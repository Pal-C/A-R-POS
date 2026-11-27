"""checkout_sale and replace_draft_cart (specs/006-sales-ui R1–R3)."""

import threading
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase

from customers.tests.factories import make_customer
from inventory.models import InventoryMovement
from sales.models import Payment, Sale, SaleEvent
from sales.services import (
    checkout_sale,
    create_draft_sale,
    finalize_sale,
    replace_draft_cart,
    store_today,
)
from sales.tests.factories import line, make_product, make_user

D = Decimal


def cashier():
    return make_user(permissions=["record_payment"])


class CheckoutTests(TestCase):
    def setUp(self):
        self.user = cashier()
        self.bg66 = make_product(selling_price=D("450.00"), stock_quantity=5)
        self.grip = make_product(selling_price=D("120.00"), stock_quantity=10)

    def checkout(self, **kwargs):
        kwargs.setdefault("user", self.user)
        kwargs.setdefault("items", [line(self.bg66, 1), line(self.grip, 2)])
        sale, _created = checkout_sale(**kwargs)
        return sale

    def test_full_payment_completes_the_sale_and_deducts_stock(self):
        sale = self.checkout(
            discount_amount=D("40.00"),
            payment={"payment_method": "CASH", "amount": D("650.00")},
        )

        self.assertEqual(sale.status, Sale.Status.COMPLETED)
        self.assertEqual(sale.total_amount, D("650.00"))
        self.assertEqual(sale.amount_paid, D("650.00"))
        self.assertEqual(sale.sale_date, store_today())
        self.assertTrue(sale.sale_number)
        self.bg66.refresh_from_db()
        self.grip.refresh_from_db()
        self.assertEqual((self.bg66.stock_quantity, self.grip.stock_quantity), (4, 8))

    def test_partial_payment_leaves_pending_payment(self):
        sale = self.checkout(payment={"payment_method": "GCASH", "amount": D("300.00")})

        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertEqual(sale.balance, D("390.00"))

    def test_no_payment_is_pending_payment(self):
        sale = self.checkout()

        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertFalse(Payment.objects.exists())

    def test_same_client_transaction_id_returns_the_existing_sale(self):
        txn = uuid.uuid4()
        first, created_first = checkout_sale(
            user=self.user, items=[line(self.bg66, 1)], client_transaction_id=txn
        )
        second, created_second = checkout_sale(
            user=self.user, items=[line(self.bg66, 1)], client_transaction_id=txn
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual((created_first, created_second), (True, False))
        self.assertEqual(Sale.objects.count(), 1)
        self.bg66.refresh_from_db()
        self.assertEqual(self.bg66.stock_quantity, 4)

    def test_checkout_from_a_draft_uses_the_new_cart(self):
        draft = create_draft_sale(user=self.user, items=[line(self.grip, 1)])

        sale = self.checkout(draft_id=draft.pk, items=[line(self.bg66, 2)])

        self.assertEqual(sale.pk, draft.pk)
        self.assertEqual(
            list(sale.items.values_list("product_id", "quantity")), [(self.bg66.pk, 2)]
        )
        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)

    def test_stock_shortage_rolls_everything_back(self):
        with self.assertRaises(ValidationError) as ctx:
            self.checkout(
                items=[line(self.bg66, 6)],
                payment={"payment_method": "CASH", "amount": D("100.00")},
            )

        self.assertIn("items", ctx.exception.message_dict)
        self.assertIn("Insufficient stock", ctx.exception.message_dict["items"][0])
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(InventoryMovement.objects.exists())

    def test_rejections(self):
        inactive = make_product(is_active=False)
        cases = {
            "inactive product": dict(items=[line(inactive, 1)]),
            "empty cart": dict(items=[]),
            "duplicate product": dict(items=[line(self.bg66, 1), line(self.bg66, 1)]),
            "discount over total": dict(discount_amount=D("700.00")),
            "payment over total": dict(
                payment={"payment_method": "CASH", "amount": D("691.00")}
            ),
            "future date": dict(sale_date=store_today() + timedelta(days=1)),
        }
        for name, kwargs in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValidationError):
                    self.checkout(**kwargs)
        self.assertFalse(Sale.objects.exists())

    def test_archived_customer_is_rejected(self):
        archived = make_customer(full_name="Gone", is_active=False)

        with self.assertRaises(ValidationError):
            self.checkout(customer=archived)

    def test_payment_requires_record_payment_permission(self):
        with self.assertRaises(PermissionDenied):
            self.checkout(
                user=make_user(),
                payment={"payment_method": "CASH", "amount": D("10.00")},
            )

    def test_backdating_requires_permission_and_reason(self):
        yesterday = store_today() - timedelta(days=1)

        with self.assertRaises(PermissionDenied):
            self.checkout(sale_date=yesterday, backdate_reason="Paper receipt")

        manager = make_user(permissions=["record_payment", "backdate_sale"])
        with self.assertRaises(ValidationError) as ctx:
            self.checkout(user=manager, sale_date=yesterday, backdate_reason="  ")
        self.assertIn("backdate_reason", ctx.exception.message_dict)

        sale = self.checkout(
            user=manager, sale_date=yesterday, backdate_reason="Paper receipt"
        )

        self.assertEqual(sale.sale_date, yesterday)
        self.assertEqual(sale.finalized_at.date() >= yesterday, True)
        event = sale.events.get()
        self.assertEqual(event.action, SaleEvent.Action.BACKDATED)
        self.assertEqual(
            event.changes, {"sale_date": [str(store_today()), str(yesterday)]}
        )
        self.assertEqual(event.reason, "Paper receipt")
        self.assertEqual(event.performed_by, manager)

    def test_today_is_not_a_backdate(self):
        sale = self.checkout(sale_date=store_today())

        self.assertFalse(sale.events.exists())

    def test_finalize_sets_sale_date_for_existing_callers(self):
        draft = create_draft_sale(user=self.user, items=[line(self.bg66, 1)])

        finalize_sale(draft.pk, self.user)

        draft.refresh_from_db()
        self.assertEqual(draft.sale_date, store_today())


class ReplaceDraftCartTests(TestCase):
    def setUp(self):
        self.user = cashier()
        self.a = make_product(selling_price=D("100.00"))
        self.b = make_product(selling_price=D("50.00"))
        self.draft = create_draft_sale(user=self.user, items=[line(self.a, 1)])

    def test_replaces_lines_customer_and_discount(self):
        customer = make_customer(full_name="Ana Reyes")

        sale = replace_draft_cart(
            sale_id=self.draft.pk,
            items=[line(self.b, 3)],
            customer=customer,
            discount_amount=D("10.00"),
        )

        self.assertEqual(
            list(sale.items.values_list("product_id", "quantity")), [(self.b.pk, 3)]
        )
        self.assertEqual(sale.customer, customer)
        self.assertEqual(sale.total_amount, D("140.00"))

    def test_only_drafts_can_be_replaced(self):
        finalize_sale(self.draft.pk, self.user)

        with self.assertRaises(ValidationError):
            replace_draft_cart(sale_id=self.draft.pk, items=[line(self.b, 1)])

    def test_rejects_empty_and_discount_over_total(self):
        for kwargs in (
            dict(items=[]),
            dict(items=[line(self.b, 1)], discount_amount=D("60.00")),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                replace_draft_cart(sale_id=self.draft.pk, **kwargs)


class CheckoutConcurrencyTests(TransactionTestCase):
    def test_two_checkouts_for_the_last_unit(self):
        user = cashier()
        product = make_product(stock_quantity=1)
        barrier = threading.Barrier(2)
        results = []

        def attempt():
            try:
                barrier.wait()
                results.append(checkout_sale(user=user, items=[line(product, 1)]))
            except Exception as exc:  # noqa: BLE001 — collected for assertions
                results.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        errors = [r for r in results if isinstance(r, ValidationError)]
        self.assertEqual(len(errors), 1)
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 0)
        self.assertEqual(Sale.objects.exclude(status=Sale.Status.DRAFT).count(), 1)


class CheckoutReviewFixTests(TestCase):
    """Regression tests for the 006 code-review findings."""

    def setUp(self):
        self.user = cashier()
        self.product = make_product(selling_price=D("100.00"), stock_quantity=10)

    def test_unknown_draft_is_a_validation_error(self):
        with self.assertRaises(ValidationError) as ctx:
            checkout_sale(
                user=self.user, items=[line(self.product, 1)], draft_id=999999
            )

        self.assertIn("draft_id", ctx.exception.message_dict)

    def test_transaction_id_only_matches_the_same_users_finalized_sale(self):
        txn = uuid.uuid4()
        mine, _ = checkout_sale(
            user=self.user, items=[line(self.product, 1)], client_transaction_id=txn
        )

        with self.assertRaises(ValidationError) as ctx:
            checkout_sale(
                user=cashier(), items=[line(self.product, 1)], client_transaction_id=txn
            )
        self.assertIn("client_transaction_id", ctx.exception.message_dict)

        again, created = checkout_sale(
            user=self.user, items=[line(self.product, 1)], client_transaction_id=txn
        )
        self.assertEqual((again.pk, created), (mine.pk, False))

    def test_transaction_id_of_a_draft_is_not_treated_as_a_repeat(self):
        draft = create_draft_sale(user=self.user, items=[line(self.product, 1)])

        with self.assertRaises(ValidationError) as ctx:
            checkout_sale(
                user=self.user,
                items=[line(self.product, 1)],
                client_transaction_id=draft.client_transaction_id,
            )

        self.assertIn("client_transaction_id", ctx.exception.message_dict)
        draft.refresh_from_db()
        self.assertEqual(draft.status, Sale.Status.DRAFT)

    def test_line_discounts_are_kept_when_completing_a_draft(self):
        draft = create_draft_sale(
            user=self.user, items=[line(self.product, 2, "30.00")]
        )

        sale, _ = checkout_sale(
            user=self.user, draft_id=draft.pk, items=[line(self.product, 2, "30.00")]
        )

        self.assertEqual(sale.items.get().discount_amount, D("30.00"))
        self.assertEqual(sale.total_amount, D("170.00"))
