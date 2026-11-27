from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from inventory.models import InventoryMovement
from sales.models import Payment, Sale, SaleItem
from sales.services import (
    add_sale_item,
    cancel_sale,
    create_draft_sale,
    finalize_sale,
    process_refund,
    record_payment,
    remove_sale_item,
    update_draft_sale,
    update_sale_item,
)
from sales.tests.factories import line, make_customer, make_product, make_user

D = Decimal


class SalesServiceTestCase(TestCase):
    def setUp(self):
        self.user = make_user()
        self.customer = make_customer()
        # 1500 / 1000, stock 10
        self.racket = make_product(name="Racket")
        # 250 / 120, stock 20
        self.grip = make_product(
            name="Grip",
            selling_price=D("250.00"),
            cost_price=D("120.00"),
            stock_quantity=20,
        )

    def draft(self, items=None, discount="0.00", customer=None):
        return create_draft_sale(
            user=self.user,
            items=items or [line(self.racket, 2, "50.00")],
            customer=customer,
            discount_amount=D(discount),
        )

    def finalized(self, **kwargs):
        sale = self.draft(**kwargs)
        return finalize_sale(sale.pk, self.user)

    def pay(self, sale, amount, method=Payment.Method.CASH):
        return record_payment(
            user=self.user,
            sale=sale,
            amount=D(amount),
            payment_method=method,
        )

    def stock(self, product):
        product.refresh_from_db()
        return product.stock_quantity


class CreateDraftSaleTests(SalesServiceTestCase):
    def test_calculates_subtotal_discounts_and_total(self):
        sale = self.draft(
            items=[line(self.racket, 2, "50.00"), line(self.grip, 3, "25.00")],
            discount="100.00",
            customer=self.customer,
        )

        # 2*1500 + 3*250 = 3750; item discounts 75; sale discount 100
        self.assertEqual(sale.subtotal, D("3750.00"))
        self.assertEqual(sale.item_discount_total, D("75.00"))
        self.assertEqual(sale.discount_amount, D("100.00"))
        self.assertEqual(sale.total_amount, D("3575.00"))
        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertEqual(sale.customer, self.customer)
        self.assertEqual(sale.created_by, self.user)
        self.assertIsNone(sale.sale_number)

    def test_snapshots_prices_and_costs(self):
        sale = self.draft()
        self.racket.selling_price = D("9999.00")
        self.racket.cost_price = D("8888.00")
        self.racket.save()

        item = sale.items.get()
        self.assertEqual(item.unit_selling_price, D("1500.00"))
        self.assertEqual(item.unit_cost_price, D("1000.00"))

    def test_does_not_touch_inventory(self):
        self.draft()
        self.assertEqual(self.stock(self.racket), 10)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_sale_discount_can_equal_remaining_amount(self):
        sale = self.draft(items=[line(self.grip, 1)], discount="250.00")
        self.assertEqual(sale.total_amount, D("0.00"))

    def test_rejections(self):
        inactive = make_product(is_active=False)
        archived = make_customer(is_active=False)
        cases = {
            "no items": dict(items=[]),
            "duplicate product": dict(
                items=[line(self.racket, 1), line(self.racket, 2)]
            ),
            "zero quantity": dict(items=[line(self.racket, 0)]),
            "negative quantity": dict(items=[line(self.racket, -1)]),
            "negative item discount": dict(items=[line(self.racket, 1, "-1.00")]),
            "item discount above line": dict(items=[line(self.racket, 1, "1500.01")]),
            "negative sale discount": dict(
                items=[line(self.racket, 1)], discount_amount=D("-1.00")
            ),
            "sale discount above remaining": dict(
                items=[line(self.racket, 1, "500.00")],
                discount_amount=D("1000.01"),
            ),
            "inactive product": dict(items=[line(inactive, 1)]),
            "archived customer": dict(items=[line(self.racket, 1)], customer=archived),
        }

        for name, kwargs in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValidationError):
                    create_draft_sale(user=self.user, **kwargs)

        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)


class EditDraftSaleTests(SalesServiceTestCase):
    def test_add_new_product_creates_line_and_updates_totals(self):
        sale = self.draft()  # 3000 - 50 = 2950

        item = add_sale_item(
            sale_id=sale.pk, product=self.grip, quantity=2, discount_amount=D("10")
        )

        sale.refresh_from_db()
        self.assertEqual(item.unit_selling_price, D("250.00"))
        self.assertEqual(item.unit_cost_price, D("120.00"))
        self.assertEqual(sale.subtotal, D("3500.00"))
        self.assertEqual(sale.total_amount, D("3440.00"))

    def test_add_existing_product_merges_line_and_keeps_snapshot(self):
        sale = self.draft()
        self.racket.selling_price = D("2000.00")
        self.racket.save()

        add_sale_item(sale_id=sale.pk, product=self.racket, quantity=1)

        item = sale.items.get()
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.unit_selling_price, D("1500.00"))
        sale.refresh_from_db()
        self.assertEqual(sale.subtotal, D("4500.00"))

    def test_update_item_quantity_and_discount(self):
        sale = self.draft()
        item = sale.items.get()

        update_sale_item(
            sale_id=sale.pk, item_id=item.pk, quantity=4, discount_amount=D("0")
        )

        sale.refresh_from_db()
        self.assertEqual(sale.subtotal, D("6000.00"))
        self.assertEqual(sale.total_amount, D("6000.00"))

    def test_remove_item(self):
        sale = self.draft(items=[line(self.racket, 1), line(self.grip, 1)])
        remove_sale_item(sale_id=sale.pk, item_id=sale.items.get(product=self.grip).pk)

        sale.refresh_from_db()
        self.assertEqual(sale.items.count(), 1)
        self.assertEqual(sale.total_amount, D("1500.00"))

    def test_update_customer_and_discount(self):
        sale = self.draft()

        update_draft_sale(
            sale_id=sale.pk, customer=self.customer, discount_amount=D("950.00")
        )
        sale.refresh_from_db()
        self.assertEqual(sale.customer, self.customer)
        self.assertEqual(sale.total_amount, D("2000.00"))

        update_draft_sale(sale_id=sale.pk, customer=None)
        sale.refresh_from_db()
        self.assertIsNone(sale.customer)
        self.assertEqual(sale.discount_amount, D("950.00"))

    def test_shrinking_sale_below_discount_is_rejected(self):
        sale = self.draft(items=[line(self.racket, 2)], discount="2000.00")
        item = sale.items.get()

        with self.assertRaises(ValidationError):
            update_sale_item(sale_id=sale.pk, item_id=item.pk, quantity=1)

        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    def test_edit_rejections(self):
        sale = self.draft()
        item = sale.items.get()
        cases = {
            "add zero quantity": lambda: add_sale_item(
                sale_id=sale.pk, product=self.grip, quantity=0
            ),
            "add inactive product": lambda: add_sale_item(
                sale_id=sale.pk, product=make_product(is_active=False), quantity=1
            ),
            "merge discount above line": lambda: add_sale_item(
                sale_id=sale.pk,
                product=self.racket,
                quantity=1,
                discount_amount=D("4500.00"),
            ),
            "update zero quantity": lambda: update_sale_item(
                sale_id=sale.pk, item_id=item.pk, quantity=0
            ),
            "update negative discount": lambda: update_sale_item(
                sale_id=sale.pk, item_id=item.pk, discount_amount=D("-1")
            ),
            "sale discount above remaining": lambda: update_draft_sale(
                sale_id=sale.pk, discount_amount=D("2950.01")
            ),
            "archived customer": lambda: update_draft_sale(
                sale_id=sale.pk, customer=make_customer(is_active=False)
            ),
        }
        for name, call in cases.items():
            with self.subTest(name), self.assertRaises(ValidationError):
                call()

    def test_finalized_sale_cannot_be_edited(self):
        sale = self.finalized()
        item = sale.items.get()
        calls = [
            lambda: add_sale_item(sale_id=sale.pk, product=self.grip, quantity=1),
            lambda: update_sale_item(sale_id=sale.pk, item_id=item.pk, quantity=1),
            lambda: remove_sale_item(sale_id=sale.pk, item_id=item.pk),
            lambda: update_draft_sale(sale_id=sale.pk, discount_amount=D("1")),
        ]
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ValidationError):
                call()


class FinalizeSaleTests(SalesServiceTestCase):
    def test_deducts_inventory_and_records_movements(self):
        sale = self.finalized(items=[line(self.racket, 2), line(self.grip, 5)])

        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertIsNotNone(sale.finalized_at)
        self.assertEqual(self.stock(self.racket), 8)
        self.assertEqual(self.stock(self.grip), 15)

        movements = InventoryMovement.objects.filter(sale_item__sale=sale)
        self.assertEqual(movements.count(), 2)
        for movement in movements:
            self.assertEqual(
                movement.movement_type, InventoryMovement.MovementType.SALE
            )
            self.assertEqual(movement.quantity_change, -movement.sale_item.quantity)
            self.assertEqual(movement.reference_number, sale.sale_number)
            self.assertEqual(movement.created_by, self.user)

    def test_assigns_sale_number(self):
        sale = self.finalized()
        self.assertRegex(sale.sale_number, rf"^S\d{{8}}-{sale.pk:06d}$")

    def test_totals_come_from_snapshots_not_current_prices(self):
        sale = self.draft()
        self.racket.selling_price = D("1.00")
        self.racket.save()

        sale = finalize_sale(sale.pk, self.user)
        self.assertEqual(sale.total_amount, D("2950.00"))

    def test_zero_total_sale_is_completed(self):
        sale = self.finalized(items=[line(self.grip, 1, "250.00")])
        self.assertEqual(sale.status, Sale.Status.COMPLETED)

    def test_insufficient_stock_rolls_back_everything(self):
        sale = self.draft(items=[line(self.grip, 1), line(self.racket, 11)])

        with self.assertRaises(ValidationError):
            finalize_sale(sale.pk, self.user)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertIsNone(sale.sale_number)
        self.assertEqual(self.stock(self.grip), 20)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_product_deactivated_after_draft_is_rejected(self):
        sale = self.draft()
        self.racket.is_active = False
        self.racket.save()

        with self.assertRaises(ValidationError):
            finalize_sale(sale.pk, self.user)
        self.assertEqual(self.stock(self.racket), 10)

    def test_empty_draft_cannot_be_finalized(self):
        sale = self.draft()
        remove_sale_item(sale_id=sale.pk, item_id=sale.items.get().pk)

        with self.assertRaises(ValidationError):
            finalize_sale(sale.pk, self.user)

    def test_cannot_finalize_twice(self):
        sale = self.finalized()
        with self.assertRaises(ValidationError):
            finalize_sale(sale.pk, self.user)
        self.assertEqual(self.stock(self.racket), 8)


class PaymentTests(SalesServiceTestCase):
    def test_partial_then_full_payment(self):
        sale = self.finalized()  # total 2950

        self.pay(sale, "1000.00")
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertEqual(sale.amount_paid, D("1000.00"))
        self.assertEqual(sale.balance, D("1950.00"))

        self.pay(sale, "1950.00", method=Payment.Method.GCASH)
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.COMPLETED)
        self.assertEqual(sale.amount_paid, D("2950.00"))
        self.assertEqual(sale.balance, D("0.00"))

    def test_payment_records_audit_fields(self):
        sale = self.finalized()
        payment = record_payment(
            user=self.user,
            sale=sale,
            amount=D("100.00"),
            payment_method=Payment.Method.CARD,
            reference_number="APPROVAL-1",
        )
        self.assertEqual(payment.received_by, self.user)
        self.assertEqual(payment.status, Payment.Status.POSTED)
        self.assertEqual(payment.payment_type, Payment.PaymentType.RECEIPT)
        self.assertEqual(payment.reference_number, "APPROVAL-1")

    def test_voided_payments_are_ignored(self):
        sale = self.finalized()
        payment = self.pay(sale, "500.00")
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.VOIDED)

        sale.refresh_from_db()
        self.assertEqual(sale.amount_paid, D("0.00"))
        # The voided amount no longer counts toward the balance limit.
        self.pay(sale, "2950.00")

    def test_payment_rejections(self):
        draft = self.draft()
        sale = self.finalized()
        cases = {
            "draft sale": dict(sale=draft, amount=D("1")),
            "zero amount": dict(sale=sale, amount=D("0")),
            "negative amount": dict(sale=sale, amount=D("-5")),
            "above balance": dict(sale=sale, amount=D("2950.01")),
            "bad method": dict(sale=sale, amount=D("1"), payment_method="BITCOIN"),
            "no target": dict(amount=D("1")),
        }
        for name, kwargs in cases.items():
            kwargs.setdefault("payment_method", Payment.Method.CASH)
            with self.subTest(name), self.assertRaises(ValidationError):
                record_payment(user=self.user, **kwargs)

        self.assertFalse(Payment.objects.exists())


class RefundTests(SalesServiceTestCase):
    def refund(self, sale, amount, reason="Overcharged"):
        return process_refund(
            user=self.user,
            sale=sale,
            amount=D(amount),
            payment_method=Payment.Method.CASH,
            reason=reason,
        )

    def test_partial_refund_reopens_balance(self):
        sale = self.finalized()
        self.pay(sale, "2950.00")

        refund = self.refund(sale, "200.00", reason="  Price match  ")

        sale.refresh_from_db()
        self.assertEqual(refund.payment_type, Payment.PaymentType.REFUND)
        self.assertEqual(refund.notes, "Price match")
        self.assertEqual(sale.amount_paid, D("2750.00"))
        self.assertEqual(sale.balance, D("200.00"))
        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)

    def test_refund_does_not_change_inventory(self):
        sale = self.finalized()
        self.pay(sale, "2950.00")
        self.refund(sale, "2950.00")
        self.assertEqual(self.stock(self.racket), 8)

    def test_refund_rejections(self):
        sale = self.finalized()
        self.pay(sale, "1000.00")

        with self.subTest("no reason"), self.assertRaises(ValidationError):
            self.refund(sale, "10.00", reason=" ")
        with self.subTest("above received"), self.assertRaises(ValidationError):
            self.refund(sale, "1000.01")

        self.refund(sale, "600.00")
        with self.subTest("above remaining after refund"):
            with self.assertRaises(ValidationError):
                self.refund(sale, "400.01")


class CancelSaleTests(SalesServiceTestCase):
    def cancel(self, sale, reason="Customer changed their mind"):
        return cancel_sale(sale_id=sale.pk, user=self.user, reason=reason)

    def test_reverses_every_inventory_deduction(self):
        sale = self.finalized(items=[line(self.racket, 2), line(self.grip, 5)])

        sale = self.cancel(sale)

        self.assertEqual(sale.status, Sale.Status.CANCELLED)
        self.assertEqual(sale.cancelled_by, self.user)
        self.assertIsNotNone(sale.cancelled_at)
        self.assertEqual(sale.cancellation_reason, "Customer changed their mind")
        self.assertEqual(self.stock(self.racket), 10)
        self.assertEqual(self.stock(self.grip), 20)

        # Original movements are kept; each has exactly one reversal.
        originals = InventoryMovement.objects.filter(
            sale_item__sale=sale,
            movement_type=InventoryMovement.MovementType.SALE,
        )
        self.assertEqual(originals.count(), 2)
        for movement in originals:
            reversal = movement.reversals.get()
            self.assertEqual(reversal.quantity_change, -movement.quantity_change)
            self.assertEqual(reversal.reference_number, sale.sale_number)

    def test_completed_sale_can_be_cancelled_then_refunded(self):
        sale = self.finalized()
        self.pay(sale, "2950.00")

        sale = self.cancel(sale)
        sale.refresh_from_db()
        self.assertEqual(sale.balance, D("0.00"))
        self.assertEqual(sale.refund_due, D("2950.00"))

        process_refund(
            user=self.user,
            sale=sale,
            amount=D("2950.00"),
            payment_method=Payment.Method.CASH,
            reason="Sale cancelled",
        )
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.CANCELLED)
        self.assertEqual(sale.refund_due, D("0.00"))

        with self.assertRaises(ValidationError):
            self.pay(sale, "1.00")

    def test_cancel_rejections(self):
        draft = self.draft()
        sale = self.finalized()

        with self.subTest("draft"), self.assertRaises(ValidationError):
            self.cancel(draft)
        with self.subTest("blank reason"), self.assertRaises(ValidationError):
            self.cancel(sale, reason="   ")

        self.cancel(sale)
        with self.subTest("twice"), self.assertRaises(ValidationError):
            self.cancel(sale)

        # Stock was restored exactly once.
        self.assertEqual(self.stock(self.racket), 10)


class ArchivedCustomerSaleTests(SalesServiceTestCase):
    """Archived customers cannot be used on sales (customers FR-017)."""

    def archive(self, customer):
        from customers.services import archive_customer

        archive_customer(customer.pk, self.user)
        customer.refresh_from_db()

    def test_finalize_refuses_draft_whose_customer_was_archived(self):
        sale = self.draft(customer=self.customer)
        self.archive(self.customer)

        with self.assertRaises(ValidationError):
            finalize_sale(sale.pk, self.user)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertEqual(self.stock(self.racket), 10)

    def test_create_and_update_refuse_archived_customer(self):
        sale = self.draft()
        self.archive(self.customer)

        with self.assertRaises(ValidationError):
            self.draft(customer=self.customer)
        with self.assertRaises(ValidationError):
            update_draft_sale(sale_id=sale.pk, customer=self.customer)

    def test_customer_check_adds_at_most_one_query_to_finalize(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def finalize_queries(customer):
            sale = self.draft(items=[line(self.grip, 1)], customer=customer)
            with CaptureQueriesContext(connection) as ctx:
                finalize_sale(sale.pk, self.user)
            return len(ctx.captured_queries)

        walk_in = finalize_queries(None)
        with_customer = finalize_queries(self.customer)
        self.assertLessEqual(with_customer - walk_in, 1)


class StringingPaymentSyncTests(TestCase):
    """record_payment keeps a stringing order's paid_in_full_at current
    (stringing research R2) without adding queries to sale payments."""

    def test_stringing_payment_through_sales_service_updates_paid_in_full(self):
        from stringing.tests.factories import make_order

        user = make_user()
        order = make_order(user)  # total 400
        record_payment(
            user=user,
            amount=Decimal("400.00"),
            payment_method=Payment.Method.CASH,
            stringing_order=order,
        )
        order.refresh_from_db()
        self.assertIsNotNone(order.paid_in_full_at)

        process_refund(
            user=user,
            amount=Decimal("10.00"),
            payment_method=Payment.Method.CASH,
            reason="Adjust",
            stringing_order=order,
        )
        order.refresh_from_db()
        self.assertIsNone(order.paid_in_full_at)

    def test_sale_payment_query_count_unchanged(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        user = make_user()
        sale = create_draft_sale(user=user, items=[line(make_product(), 1)])
        sale = finalize_sale(sale.pk, user)
        with CaptureQueriesContext(connection) as ctx:
            record_payment(
                user=user,
                amount=Decimal("100.00"),
                payment_method=Payment.Method.CASH,
                sale=sale,
            )
        sql = [q["sql"] for q in ctx.captured_queries if "SAVEPOINT" not in q["sql"]]
        # Lock sale, net received, insert payment, update status; nothing
        # from the stringing app.
        self.assertEqual(len(sql), 4, sql)
        self.assertFalse(any("stringing" in q.split(" FROM ")[-1][:40] for q in sql))


class PreOrderPaymentRuleTests(TestCase):
    """record_payment refuses receipts on fulfilled pre-orders (preorders R2)."""

    def test_fulfilled_preorder_refuses_receipts_allows_refunds(self):
        from preorders.models import PreOrder
        from preorders.services import change_status, fulfill_preorder
        from preorders.tests.factories import make_preorder

        user = make_user()
        preorder = make_preorder(user, quantity=1, agreed_unit_price=Decimal("100.00"))
        record_payment(
            user=user,
            amount=Decimal("100.00"),
            payment_method=Payment.Method.CASH,
            preorder=preorder,
        )
        for status in (PreOrder.Status.ORDERED, PreOrder.Status.ARRIVED):
            change_status(preorder_id=preorder.pk, user=user, to_status=status)
        preorder = fulfill_preorder(preorder_id=preorder.pk, user=user)

        process_refund(
            user=user,
            amount=Decimal("20.00"),
            payment_method=Payment.Method.CASH,
            reason="Goodwill",
            preorder=preorder,
        )
        with self.assertRaises(ValidationError):
            record_payment(
                user=user,
                amount=Decimal("20.00"),
                payment_method=Payment.Method.CASH,
                preorder=preorder,
            )
