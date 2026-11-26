"""
End-to-end tests of the sales workflow through the HTTP API:
draft → edit → finalize → pay → refund → cancel, plus access control,
query budgets, and concurrent finalization.
"""

import threading
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from inventory.models import InventoryMovement
from sales.models import Payment, Sale
from sales.services import create_draft_sale, finalize_sale
from sales.tests.factories import line, make_customer, make_product, make_user

D = Decimal


class SalesWorkflowAPITests(APITestCase):
    def setUp(self):
        self.cashier = make_user(username="cashier", permissions=["record_payment"])
        self.manager = make_user(
            username="manager",
            permissions=["cancel_sale", "process_refund", "record_payment"],
        )
        self.customer = make_customer(full_name="Ana Reyes")
        self.racket = make_product(name="Racket", stock_quantity=10)  # 1500/1000
        self.grip = make_product(
            name="Grip",
            selling_price=D("250.00"),
            cost_price=D("120.00"),
            stock_quantity=20,
        )
        self.shoes = make_product(
            name="Shoes",
            selling_price=D("3200.00"),
            cost_price=D("2100.00"),
            stock_quantity=4,
        )
        self.client.force_authenticate(self.cashier)

    # -- helpers ---------------------------------------------------------

    def post(self, url, data=None, expected=200):
        response = self.client.post(url, data or {}, format="json")
        self.assertEqual(response.status_code, expected, response.data)
        return response.data

    def patch(self, url, data, expected=200):
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, expected, response.data)
        return response.data

    def stock(self, product):
        product.refresh_from_db()
        return product.stock_quantity

    def as_user(self, user):
        self.client.force_authenticate(user)

    # -- the full happy path ------------------------------------------------

    def test_complete_sale_lifecycle(self):
        # 1. Cashier opens a draft for a customer with one racket.
        sale = self.post(
            reverse("sale-list-create"),
            {
                "customer_id": self.customer.pk,
                "items": [{"product_id": self.racket.pk, "quantity": 1}],
            },
            expected=201,
        )
        sale_id = sale["id"]
        self.assertEqual(sale["status"], "DRAFT")
        self.assertEqual(sale["total_amount"], "1500.00")

        # 2. Scans two grips, then the same racket again (merges into its line).
        items_url = reverse("sale-item-add", kwargs={"pk": sale_id})
        self.post(items_url, {"product_id": self.grip.pk, "quantity": 2}, 201)
        sale = self.post(items_url, {"product_id": self.racket.pk, "quantity": 1}, 201)
        self.assertEqual(len(sale["items"]), 2)
        racket_line = next(i for i in sale["items"] if i["product"] == self.racket.pk)
        self.assertEqual(racket_line["quantity"], 2)

        # 3. Adds shoes, then removes them.
        sale = self.post(items_url, {"product_id": self.shoes.pk, "quantity": 1}, 201)
        shoes_line = next(i for i in sale["items"] if i["product"] == self.shoes.pk)
        response = self.client.delete(
            reverse(
                "sale-item-detail", kwargs={"pk": sale_id, "item_pk": shoes_line["id"]}
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 2)

        # 4. Applies a 100 discount on the racket line and 50 on the sale.
        self.patch(
            reverse(
                "sale-item-detail",
                kwargs={"pk": sale_id, "item_pk": racket_line["id"]},
            ),
            {"discount_amount": "100.00"},
        )
        sale = self.patch(
            reverse("sale-detail", kwargs={"pk": sale_id}),
            {"discount_amount": "50.00"},
        )
        # 2*1500 + 2*250 = 3500; item discounts 100; sale discount 50
        self.assertEqual(sale["subtotal"], "3500.00")
        self.assertEqual(sale["item_discount_total"], "100.00")
        self.assertEqual(sale["discount_amount"], "50.00")
        self.assertEqual(sale["total_amount"], "3350.00")
        self.assertEqual(sale["balance"], "0.00")  # drafts owe nothing yet

        # Price changes after the draft do not affect it.
        self.racket.selling_price = D("1800.00")
        self.racket.save()

        # Nothing has left the shelf yet.
        self.assertEqual(self.stock(self.racket), 10)
        self.assertEqual(self.stock(self.grip), 20)

        # 5. Finalize: stock is deducted, sale is numbered and awaits payment.
        sale = self.post(reverse("sale-finalize", kwargs={"pk": sale_id}))
        self.assertEqual(sale["status"], "PENDING_PAYMENT")
        self.assertEqual(sale["total_amount"], "3350.00")
        self.assertTrue(sale["sale_number"])
        self.assertEqual(sale["balance"], "3350.00")
        self.assertEqual(self.stock(self.racket), 8)
        self.assertEqual(self.stock(self.grip), 18)

        # Finalized sales are locked for editing.
        self.post(items_url, {"product_id": self.grip.pk, "quantity": 1}, 400)
        self.patch(
            reverse("sale-detail", kwargs={"pk": sale_id}),
            {"discount_amount": "0.00"},
            expected=400,
        )

        # 6. Customer pays in two parts.
        payments_url = reverse("payment-list-create")
        self.post(
            payments_url,
            {"sale": sale_id, "amount": "2000.00", "payment_method": "CASH"},
            201,
        )
        sale = self.client.get(reverse("sale-detail", kwargs={"pk": sale_id})).data
        self.assertEqual(sale["amount_paid"], "2000.00")
        self.assertEqual(sale["balance"], "1350.00")
        self.assertEqual(sale["status"], "PENDING_PAYMENT")

        self.post(
            payments_url,
            {"sale": sale_id, "amount": "1350.01", "payment_method": "GCASH"},
            400,
        )
        self.post(
            payments_url,
            {"sale": sale_id, "amount": "1350.00", "payment_method": "GCASH"},
            201,
        )
        sale = self.client.get(reverse("sale-detail", kwargs={"pk": sale_id})).data
        self.assertEqual(sale["status"], "COMPLETED")
        self.assertEqual(sale["balance"], "0.00")
        self.assertEqual(len(sale["payments"]), 2)

        # 7. A cashier cannot refund or cancel; a manager can.
        refund = {
            "sale": sale_id,
            "amount": "100.00",
            "payment_method": "CASH",
            "payment_type": "REFUND",
            "notes": "Grip had a defect",
        }
        self.post(payments_url, refund, 403)
        self.post(reverse("sale-cancel", kwargs={"pk": sale_id}), {"reason": "x"}, 403)

        self.as_user(self.manager)
        self.post(payments_url, refund, 201)
        sale = self.client.get(reverse("sale-detail", kwargs={"pk": sale_id})).data
        self.assertEqual(sale["amount_paid"], "3250.00")
        self.assertEqual(sale["balance"], "100.00")
        self.assertEqual(sale["status"], "PENDING_PAYMENT")
        # Money-only refunds leave stock alone.
        self.assertEqual(self.stock(self.racket), 8)

        # 8. Manager cancels: stock comes back, remaining money is owed back.
        sale = self.post(
            reverse("sale-cancel", kwargs={"pk": sale_id}),
            {"reason": "Customer returned everything"},
        )
        self.assertEqual(sale["status"], "CANCELLED")
        self.assertEqual(sale["cancellation_reason"], "Customer returned everything")
        self.assertEqual(sale["cancelled_by"], self.manager.pk)
        self.assertEqual(sale["balance"], "0.00")
        self.assertEqual(sale["refund_due"], "3250.00")
        self.assertEqual(self.stock(self.racket), 10)
        self.assertEqual(self.stock(self.grip), 20)

        # No more money can be taken; the rest is refunded.
        self.post(
            payments_url,
            {"sale": sale_id, "amount": "1.00", "payment_method": "CASH"},
            400,
        )
        self.post(
            payments_url,
            {**refund, "amount": "3250.00", "notes": "Sale cancelled"},
            201,
        )
        sale = self.client.get(reverse("sale-detail", kwargs={"pk": sale_id})).data
        self.assertEqual(sale["refund_due"], "0.00")
        self.assertEqual(sale["amount_paid"], "0.00")

        # 9. The audit trail is complete and unchanged.
        movements = InventoryMovement.objects.filter(reference_number=sale["sale_number"])
        self.assertEqual(
            sorted(movements.values_list("movement_type", "quantity_change")),
            [("REVERSAL", 2), ("REVERSAL", 2), ("SALE", -2), ("SALE", -2)],
        )
        self.assertEqual(
            list(
                Payment.objects.filter(sale_id=sale_id)
                .order_by("pk")
                .values_list("payment_type", "amount")
            ),
            [
                ("RECEIPT", D("2000.00")),
                ("RECEIPT", D("1350.00")),
                ("REFUND", D("100.00")),
                ("REFUND", D("3250.00")),
            ],
        )

        # Cancelled sales cannot be cancelled again or re-finalized.
        self.post(reverse("sale-cancel", kwargs={"pk": sale_id}), {"reason": "x"}, 400)
        self.post(reverse("sale-finalize", kwargs={"pk": sale_id}), expected=400)

    # -- failure paths through the API ------------------------------------

    def test_finalize_with_insufficient_stock_returns_400_and_changes_nothing(self):
        sale = self.post(
            reverse("sale-list-create"),
            {
                "items": [
                    {"product_id": self.grip.pk, "quantity": 1},
                    {"product_id": self.shoes.pk, "quantity": 5},
                ]
            },
            expected=201,
        )

        response = self.client.post(reverse("sale-finalize", kwargs={"pk": sale["id"]}))

        self.assertEqual(response.status_code, 400)
        self.assertIn("Insufficient stock for Shoes", str(response.data))
        self.assertEqual(self.stock(self.grip), 20)
        self.assertEqual(Sale.objects.get(pk=sale["id"]).status, Sale.Status.DRAFT)

    def test_unknown_ids_return_404(self):
        self.as_user(self.manager)
        urls = [
            ("get", reverse("sale-detail", kwargs={"pk": 999999})),
            ("post", reverse("sale-finalize", kwargs={"pk": 999999})),
            ("post", reverse("sale-cancel", kwargs={"pk": 999999})),
            ("post", reverse("sale-item-add", kwargs={"pk": 999999})),
            ("patch", reverse("sale-item-detail", kwargs={"pk": 1, "item_pk": 999999})),
            ("delete", reverse("sale-item-detail", kwargs={"pk": 1, "item_pk": 999999})),
        ]
        for method, url in urls:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {"reason": "x"}, format="json")
                self.assertEqual(response.status_code, 404)

    def test_item_from_another_sale_returns_404(self):
        first = create_draft_sale(user=self.cashier, items=[line(self.racket, 1)])
        second = create_draft_sale(user=self.cashier, items=[line(self.grip, 1)])

        response = self.client.delete(
            reverse(
                "sale-item-detail",
                kwargs={"pk": second.pk, "item_pk": first.items.get().pk},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(first.items.count(), 1)

    def test_unauthenticated_requests_are_rejected(self):
        self.client.force_authenticate(None)
        sale = create_draft_sale(user=self.cashier, items=[line(self.racket, 1)])
        requests = [
            ("get", reverse("sale-list-create")),
            ("post", reverse("sale-list-create")),
            ("get", reverse("sale-detail", kwargs={"pk": sale.pk})),
            ("post", reverse("sale-item-add", kwargs={"pk": sale.pk})),
            ("post", reverse("sale-finalize", kwargs={"pk": sale.pk})),
            ("post", reverse("sale-cancel", kwargs={"pk": sale.pk})),
            ("get", reverse("payment-list-create")),
            ("post", reverse("payment-list-create")),
        ]
        for method, url in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {}, format="json")
                self.assertIn(response.status_code, (401, 403))

        self.assertEqual(self.stock(self.racket), 10)

    # -- query budgets -----------------------------------------------------

    def query_count(self, url):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def make_paid_sale(self, items=None):
        sale = create_draft_sale(
            user=self.cashier,
            customer=make_customer(),
            items=items or [line(self.grip, 1), line(self.racket, 1)],
        )
        sale = finalize_sale(sale.pk, self.cashier)
        self.client.post(
            reverse("payment-list-create"),
            {"sale": sale.pk, "amount": "100.00", "payment_method": "CASH"},
            format="json",
        )
        return sale

    def test_sale_list_query_count_does_not_grow_with_sales(self):
        self.make_paid_sale()
        one = self.query_count(reverse("sale-list-create"))

        for _ in range(5):
            self.make_paid_sale()
        six = self.query_count(reverse("sale-list-create"))

        self.assertEqual(one, six)

    def test_sale_detail_query_count_does_not_grow_with_lines(self):
        small = self.make_paid_sale()
        big = self.make_paid_sale(items=[line(make_product(), 1) for _ in range(6)])
        self.assertEqual(
            self.query_count(reverse("sale-detail", kwargs={"pk": small.pk})),
            self.query_count(reverse("sale-detail", kwargs={"pk": big.pk})),
        )


class ConcurrentFinalizeTests(TransactionTestCase):
    """
    Two cashiers finalize sales for the last unit of a product at the same
    time. Row locking must let exactly one succeed and never oversell.
    """

    def test_last_unit_is_sold_only_once(self):
        user = make_user()
        product = make_product(stock_quantity=1)
        sales = [
            create_draft_sale(user=user, items=[line(product, 1)]) for _ in range(2)
        ]

        barrier = threading.Barrier(len(sales))
        outcomes = []

        def finalize(sale_id):
            try:
                barrier.wait(timeout=5)
                finalize_sale(sale_id, user)
                outcomes.append("ok")
            except Exception as exc:  # noqa: BLE001 - outcome is asserted below
                outcomes.append(type(exc).__name__)
            finally:
                connection.close()

        threads = [threading.Thread(target=finalize, args=(s.pk,)) for s in sales]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        self.assertEqual(sorted(outcomes), ["ValidationError", "ok"])
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 0)
        self.assertEqual(
            InventoryMovement.objects.filter(product=product).count(), 1
        )
        self.assertEqual(
            sorted(Sale.objects.values_list("status", flat=True)),
            [Sale.Status.DRAFT, Sale.Status.PENDING_PAYMENT],
        )
