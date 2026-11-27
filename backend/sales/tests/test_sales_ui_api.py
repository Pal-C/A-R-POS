"""Sales API additions for the sales screens (contracts/sales-api.md)."""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from customers.tests.factories import make_customer
from sales.models import Sale
from sales.services import (
    cancel_sale,
    checkout_sale,
    create_draft_sale,
    process_refund,
    record_payment,
    store_today,
)
from sales.tests.factories import line, make_product, make_user

D = Decimal


def grant_cost(user):
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="catalog", codename="view_product_cost"
        )
    )
    for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        user.__dict__.pop(attr, None)
    return user


class CheckoutApiTests(APITestCase):
    url = "/api/sales/checkout/"

    def setUp(self):
        self.cashier = make_user(permissions=["record_payment"])
        self.bg66 = make_product(
            name="BG66 Ultimax", selling_price=D("450.00"), stock_quantity=1
        )
        self.client.force_authenticate(self.cashier)

    def body(self, **overrides):
        data = {
            "client_transaction_id": str(uuid.uuid4()),
            "items": [{"product_id": self.bg66.pk, "quantity": 1}],
            "payment": {"payment_method": "CASH", "amount": "450.00"},
        }
        data.update(overrides)
        return data

    def test_reverse_names_exist(self):
        self.assertEqual(reverse("sale-checkout"), self.url)

    def test_checkout_returns_201_and_a_repeat_returns_200(self):
        body = self.body()

        first = self.client.post(self.url, body, format="json")
        second = self.client.post(self.url, body, format="json")

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["status"], "COMPLETED")
        self.assertEqual(first.data["sale_date"], str(store_today()))
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["id"], first.data["id"])
        self.assertEqual(Sale.objects.count(), 1)

    def test_stock_shortage_is_reported_under_items(self):
        response = self.client.post(
            self.url,
            self.body(items=[{"product_id": self.bg66.pk, "quantity": 2}]),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Insufficient stock for BG66 Ultimax", response.data["items"][0])

    def test_validation_and_permission_errors(self):
        yesterday = str(store_today() - timedelta(days=1))
        tomorrow = str(store_today() + timedelta(days=1))
        cases = [
            (self.body(items=[]), 400),
            (self.body(payment={"payment_method": "CASH", "amount": "999.00"}), 400),
            (self.body(payment={"payment_method": "BITCOIN", "amount": "1.00"}), 400),
            (self.body(sale_date=tomorrow), 400),
            (self.body(sale_date=yesterday, backdate_reason="Paper"), 403),
            (self.body(customer_id=999999), 400),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                response = self.client.post(self.url, body, format="json")
                self.assertEqual(response.status_code, expected, response.data)
        self.assertFalse(Sale.objects.exists())

    def test_payment_needs_record_payment_permission(self):
        self.client.force_authenticate(make_user())

        response = self.client.post(self.url, self.body(), format="json")

        self.assertEqual(response.status_code, 403)

    def test_anonymous_is_rejected(self):
        self.client.force_authenticate(None)
        draft = create_draft_sale(user=self.cashier, items=[line(self.bg66, 1)])
        for method, url in [
            ("post", self.url),
            ("put", f"/api/sales/{draft.pk}/draft/"),
            ("post", f"/api/sales/{draft.pk}/customer/"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(
                    getattr(self.client, method)(url, {}, format="json").status_code,
                    401,
                )

    def test_cost_fields_are_hidden_without_permission(self):
        response = self.client.post(self.url, self.body(), format="json")
        item = response.data["items"][0]
        self.assertNotIn("unit_cost_price", item)
        self.assertNotIn("gross_profit", item)

        manager = grant_cost(make_user(permissions=["record_payment"]))
        self.client.force_authenticate(manager)
        detail = self.client.get(
            reverse("sale-detail", kwargs={"pk": response.data["id"]})
        )
        self.assertIn("unit_cost_price", detail.data["items"][0])
        self.assertIn("gross_profit", detail.data["items"][0])

    def test_checkout_query_count_does_not_grow_with_lines(self):
        def count_for(n_lines):
            products = [make_product(stock_quantity=5) for _ in range(n_lines)]
            body = self.body(
                items=[{"product_id": p.pk, "quantity": 1} for p in products],
                payment=None,
            )
            body.pop("payment")
            self.cashier.has_perm("sales.record_payment")
            with CaptureQueriesContext(connection) as ctx:
                self.client.post(self.url, body, format="json")
            return len(ctx.captured_queries)

        one = count_for(1)
        three = count_for(3)
        # Linear in lines with a fixed cost per line (lock, item, stock, movement…).
        self.assertLessEqual(three - one, 2 * 10)


class DraftCartApiTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.a = make_product(selling_price=D("100.00"))
        self.b = make_product(selling_price=D("50.00"))
        self.draft = create_draft_sale(user=self.user, items=[line(self.a, 1)])
        self.url = f"/api/sales/{self.draft.pk}/draft/"
        self.client.force_authenticate(self.user)

    def test_replaces_the_cart(self):
        response = self.client.put(
            self.url,
            {
                "items": [{"product_id": self.b.pk, "quantity": 2}],
                "discount_amount": "10.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total_amount"], "90.00")
        self.assertEqual(len(response.data["items"]), 1)
        self.assertNotIn("unit_cost_price", response.data["items"][0])

    def test_non_draft_is_rejected(self):
        Sale.objects.filter(pk=self.draft.pk).update(
            status=Sale.Status.CANCELLED, sale_date=store_today()
        )

        response = self.client.put(
            self.url,
            {"items": [{"product_id": self.b.pk, "quantity": 1}]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)


class SaleListApiTests(APITestCase):
    def setUp(self):
        self.user = make_user(permissions=["record_payment", "process_refund"])
        self.client.force_authenticate(self.user)
        self.bg66 = make_product(
            name="BG66 Ultimax", selling_price=D("450.00"), stock_quantity=50
        )
        self.grip = make_product(
            name="Super Grap", selling_price=D("120.00"), stock_quantity=50
        )

    def checkout(self, items, payments=(), sale_date=None):
        sale, _ = checkout_sale(user=self.user, items=items)
        for method, amount in payments:
            record_payment(
                user=self.user, sale=sale, amount=D(amount), payment_method=method
            )
        if sale_date:
            Sale.objects.filter(pk=sale.pk).update(sale_date=sale_date)
        return sale

    def test_rows_have_summary_methods_and_date(self):
        sale = self.checkout(
            [line(self.bg66, 1), line(self.grip, 2)],
            payments=[("CASH", "300.00"), ("GCASH", "200.00"), ("CASH", "190.00")],
        )

        row = self.client.get("/api/sales/").data["results"][0]

        self.assertEqual(row["id"], sale.pk)
        self.assertEqual(row["items_summary"], "BG66 Ultimax ×1, Super Grap ×2")
        self.assertEqual(row["payment_methods"], ["CASH", "GCASH"])
        self.assertEqual(row["sale_date"], str(store_today()))

    def test_refunds_are_not_listed_as_payment_methods(self):
        sale = self.checkout([line(self.grip, 1)], payments=[("CASH", "120.00")])
        cancel_sale(sale_id=sale.pk, user=self.user, reason="Wrong item")
        process_refund(
            user=self.user,
            sale=Sale.objects.get(pk=sale.pk),
            amount=D("120.00"),
            payment_method="GCASH",
            reason="Refund",
        )

        row = self.client.get("/api/sales/").data["results"][0]

        self.assertEqual(row["payment_methods"], ["CASH"])

    def test_order_is_drafts_first_then_newest_sale_date(self):
        old = self.checkout(
            [line(self.grip, 1)], sale_date=store_today() - timedelta(days=3)
        )
        new = self.checkout([line(self.grip, 1)])
        draft = create_draft_sale(user=self.user, items=[line(self.grip, 1)])

        ids = [row["id"] for row in self.client.get("/api/sales/").data["results"]]

        self.assertEqual(ids, [draft.pk, new.pk, old.pk])

    def test_list_query_count_is_constant(self):
        for _ in range(3):
            self.checkout(
                [line(self.bg66, 1), line(self.grip, 1)], payments=[("CASH", "100.00")]
            )
        self.user.has_perm("catalog.view_product_cost")

        with self.assertNumQueries(4):
            self.client.get("/api/sales/")
        for _ in range(3):
            self.checkout([line(self.grip, 1)])
        with self.assertNumQueries(4):
            self.client.get("/api/sales/")


class SaleCustomerApiTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.ana = make_customer(full_name="Ana Reyes")
        self.archived = make_customer(full_name="Gone", is_active=False)
        self.sale, _ = checkout_sale(user=self.user, items=[line(make_product(), 1)])
        self.url = f"/api/sales/{self.sale.pk}/customer/"

    def test_links_customer_and_records_event(self):
        response = self.client.post(
            self.url,
            {"customer_id": self.ana.pk, "reason": "Asked for a receipt"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["customer"], self.ana.pk)
        event = response.data["events"][0]
        self.assertEqual(event["action"], "CUSTOMER_CHANGED")
        self.assertEqual(event["changes"], {"customer": [None, self.ana.pk]})
        self.assertEqual(event["reason"], "Asked for a receipt")
        self.assertEqual(event["performed_by"]["username"], self.user.username)

    def test_rejections(self):
        draft = create_draft_sale(user=self.user, items=[line(make_product(), 1)])
        self.client.post(
            self.url, {"customer_id": self.ana.pk, "reason": "x"}, format="json"
        )
        cases = [
            (
                self.url,
                {"customer_id": self.ana.pk, "reason": "again"},
                400,
            ),  # unchanged
            (self.url, {"customer_id": self.archived.pk, "reason": "x"}, 400),
            (self.url, {"customer_id": self.ana.pk, "reason": "  "}, 400),
            (
                f"/api/sales/{draft.pk}/customer/",
                {"customer_id": self.ana.pk, "reason": "x"},
                400,
            ),
            (
                "/api/sales/999999/customer/",
                {"customer_id": self.ana.pk, "reason": "x"},
                404,
            ),
        ]
        for url, body, expected in cases:
            with self.subTest(url=url, body=body):
                self.assertEqual(
                    self.client.post(url, body, format="json").status_code, expected
                )

    def test_cancelled_sale_is_rejected(self):
        Sale.objects.filter(pk=self.sale.pk).update(status=Sale.Status.PENDING_PAYMENT)
        cancel_sale(sale_id=self.sale.pk, user=self.user, reason="x")

        response = self.client.post(
            self.url, {"customer_id": self.ana.pk, "reason": "x"}, format="json"
        )

        self.assertEqual(response.status_code, 400)


class CancelResponseTests(APITestCase):
    def test_cancel_response_hides_cost_and_shows_refund_due(self):
        user = make_user(permissions=["record_payment", "cancel_sale"])
        self.client.force_authenticate(user)
        sale, _ = checkout_sale(
            user=user,
            items=[line(make_product(selling_price=D("450.00")), 1)],
            payment={"payment_method": "CASH", "amount": D("450.00")},
        )

        response = self.client.post(
            f"/api/sales/{sale.pk}/cancel/", {"reason": "Returned"}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "CANCELLED")
        self.assertEqual(response.data["refund_due"], "450.00")
        self.assertNotIn("unit_cost_price", response.data["items"][0])
        self.assertNotIn("gross_profit", response.data["items"][0])


class CheckoutApiReviewFixTests(APITestCase):
    def test_unknown_draft_returns_400_not_500(self):
        self.client.force_authenticate(make_user())
        product = make_product()

        response = self.client.post(
            "/api/sales/checkout/",
            {"draft_id": 999999, "items": [{"product_id": product.pk, "quantity": 1}]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("draft_id", response.data)

    def test_line_discount_is_accepted(self):
        self.client.force_authenticate(make_user())
        product = make_product(selling_price=D("100.00"))

        response = self.client.post(
            "/api/sales/checkout/",
            {
                "items": [
                    {
                        "product_id": product.pk,
                        "quantity": 2,
                        "discount_amount": "30.00",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total_amount"], "170.00")
