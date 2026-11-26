"""Service rules for pre-orders (US1–US4, US6)."""

import re
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from inventory.models import InventoryMovement
from preorders.models import PreOrder, PreOrderEvent
from preorders.selectors import store_today
from preorders.services import (
    StatusConflict,
    cancel_preorder,
    change_status,
    create_preorder,
    fulfill_preorder,
    mark_product_arrived,
    record_preorder_payment,
    update_preorder,
)
from preorders.tests.factories import (
    make_customer,
    make_payment,
    make_preorder,
    make_product,
    make_user,
)
from sales.models import Payment

S = PreOrder.Status
E = PreOrderEvent.EventType


def D(value):
    return Decimal(value)


def move(preorder, *statuses, user=None):
    for status in statuses:
        change_status(
            preorder_id=preorder.pk, user=user or preorder.created_by, to_status=status
        )
    preorder.refresh_from_db()
    return preorder


class CreatePreOrderTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.customer = make_customer()
        self.product = make_product(selling_price=D("6500.00"))

    def create(self, **overrides):
        values = {
            "user": self.user,
            "customer": self.customer,
            "product": self.product,
            "quantity": 2,
            "agreed_unit_price": D("5000.00"),
            "expected_arrival_date": store_today() + timedelta(days=21),
        }
        values.update(overrides)
        return create_preorder(**values)

    def test_creates_pending_preorder(self):
        preorder = self.create()
        self.assertEqual(preorder.status, S.PENDING)
        self.assertEqual(preorder.total_amount, D("10000.00"))
        self.assertEqual(preorder.created_by, self.user)
        event = preorder.events.get()
        self.assertEqual(event.event_type, E.CREATED)

    def test_price_defaults_to_selling_price(self):
        preorder = self.create(agreed_unit_price=None)
        self.assertEqual(preorder.agreed_unit_price, D("6500.00"))

    def test_number_format_and_increment(self):
        first, second = self.create(), self.create()
        pattern = re.compile(r"^PO-\d{4}-(\d{6})$")
        a, b = pattern.match(first.order_number), pattern.match(second.order_number)
        self.assertIsNotNone(a)
        self.assertEqual(int(b.group(1)), int(a.group(1)) + 1)

    def test_arrival_date_optional_and_today_allowed(self):
        self.assertIsNone(self.create(expected_arrival_date=None).expected_arrival_date)
        self.create(expected_arrival_date=store_today())

    def assert_field_error(self, field, **overrides):
        with self.assertRaises(ValidationError) as ctx:
            self.create(**overrides)
        self.assertIn(field, ctx.exception.message_dict)
        self.assertEqual(PreOrder.objects.count(), 0)

    def test_field_rejections(self):
        self.assert_field_error("quantity", quantity=0)
        self.assert_field_error("agreed_unit_price", agreed_unit_price=D("-1"))
        self.assert_field_error(
            "expected_arrival_date",
            expected_arrival_date=store_today() - timedelta(days=1),
        )
        self.assert_field_error("customer", customer=None)
        self.assert_field_error("product", product=None)

    def test_archived_customer_and_inactive_product_rejected(self):
        self.assert_field_error("customer", customer=make_customer(is_active=False))
        self.assert_field_error("product", product=make_product(is_active=False))


class UpdatePreOrderTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.preorder = make_preorder(self.user)  # 2 x 5000

    def update(self, can_override_price=False, **changes):
        return update_preorder(
            preorder_id=self.preorder.pk,
            user=self.user,
            can_override_price=can_override_price,
            **changes,
        )

    def test_changes_recorded(self):
        date = store_today() + timedelta(days=10)
        self.update(quantity=3, expected_arrival_date=date, notes=" Black ")
        event = self.preorder.events.get(event_type=E.UPDATED)
        self.assertEqual(
            event.changes,
            {
                "quantity": [2, 3],
                "expected_arrival_date": [None, date.isoformat()],
                "notes": ["", "Black"],
            },
        )

    def test_no_change_no_event(self):
        self.update(quantity=2)
        self.assertFalse(self.preorder.events.filter(event_type=E.UPDATED).exists())

    def test_arrived_allows_only_date_and_notes(self):
        move(self.preorder, S.ORDERED, S.ARRIVED)
        self.update(notes="Call after 5pm")
        with self.assertRaises(ValidationError) as ctx:
            self.update(quantity=1)
        self.assertIn("quantity", ctx.exception.message_dict)

    def test_final_orders_not_editable(self):
        cancel_preorder(preorder_id=self.preorder.pk, user=self.user, reason="x")
        with self.assertRaises(ValidationError):
            self.update(notes="x")

    def test_total_below_paid_refused(self):
        make_payment(self.preorder, "8000.00")
        with self.assertRaises(ValidationError):
            self.update(quantity=1)

    def test_price_change_before_payment_allowed(self):
        self.assertEqual(
            self.update(agreed_unit_price=D("4500.00")).agreed_unit_price, D("4500.00")
        )

    def test_price_change_after_payment_needs_override(self):
        make_payment(self.preorder, "1000.00")
        with self.assertRaises(PermissionDenied):
            self.update(agreed_unit_price=D("4500.00"))
        preorder = self.update(agreed_unit_price=D("4500.00"), can_override_price=True)
        self.assertEqual(preorder.agreed_unit_price, D("4500.00"))

    def test_changed_past_date_refused_unchanged_past_date_ok(self):
        with self.assertRaises(ValidationError):
            self.update(expected_arrival_date=store_today() - timedelta(days=1))
        past = store_today() - timedelta(days=5)
        PreOrder.objects.filter(pk=self.preorder.pk).update(expected_arrival_date=past)
        self.update(expected_arrival_date=past, notes="Still waiting")

    def test_unknown_field_refused(self):
        with self.assertRaises(ValidationError):
            self.update(product=make_product())


class ChangeStatusTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.preorder = make_preorder(self.user)

    def move(self, to_status, **kwargs):
        return change_status(
            preorder_id=self.preorder.pk, user=self.user, to_status=to_status, **kwargs
        )

    def test_forward_and_back_with_timestamps(self):
        order = self.move(S.ORDERED)
        self.assertIsNotNone(order.ordered_at)
        order = self.move(S.ARRIVED)
        self.assertIsNotNone(order.arrived_at)
        order = self.move(S.ORDERED)
        self.assertIsNone(order.arrived_at)
        order = self.move(S.PENDING)
        self.assertIsNone(order.ordered_at)
        self.assertEqual(
            list(
                self.preorder.events.filter(event_type=E.STATUS_CHANGED).values_list(
                    "from_status", "to_status"
                )
            ),
            [
                (S.PENDING, S.ORDERED),
                (S.ORDERED, S.ARRIVED),
                (S.ARRIVED, S.ORDERED),
                (S.ORDERED, S.PENDING),
            ],
        )

    def test_refused_transitions(self):
        for target in (S.ARRIVED, S.FULFILLED, S.CANCELLED, "DONE"):
            with self.subTest(target=target), self.assertRaises(ValidationError):
                self.move(target)

    def test_final_states(self):
        cancel_preorder(preorder_id=self.preorder.pk, user=self.user, reason="x")
        with self.assertRaises(ValidationError):
            self.move(S.ORDERED)

    def test_stale_expected_status(self):
        self.move(S.ORDERED)
        with self.assertRaises(StatusConflict) as ctx:
            self.move(S.ARRIVED, expected_status=S.PENDING)
        self.assertEqual(ctx.exception.current_status, S.ORDERED)


class MarkProductArrivedTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock_quantity=4)
        self.old_big = self.ordered(quantity=3)
        self.mid_small = self.ordered(quantity=1)
        self.new_two = self.ordered(quantity=2)
        self.pending = make_preorder(self.user, product=self.product, quantity=1)

    def ordered(self, quantity):
        return move(
            make_preorder(self.user, product=self.product, quantity=quantity), S.ORDERED
        )

    def arrive(self, received, preorder_ids=None):
        return mark_product_arrived(
            product_id=self.product.pk,
            received_quantity=received,
            user=self.user,
            preorder_ids=preorder_ids,
        )

    def statuses(self):
        return {o.pk: o.status for o in PreOrder.objects.filter(product=self.product)}

    def test_oldest_first_skipping_orders_that_do_not_fit(self):
        result = self.arrive(2)
        # The oldest (3 units) doesn't fit; the next (1) does; then 1 left, 2 doesn't fit.
        self.assertEqual([o.pk for o in result["marked"]], [self.mid_small.pk])
        self.assertEqual((result["units_used"], result["units_left"]), (1, 1))
        self.assertEqual(self.statuses()[self.old_big.pk], S.ORDERED)

    def test_oldest_first_fills_in_order(self):
        result = self.arrive(6)
        self.assertEqual(
            [o.pk for o in result["marked"]],
            [self.old_big.pk, self.mid_small.pk, self.new_two.pk],
        )
        self.assertEqual(result["units_left"], 0)
        self.assertEqual(self.statuses()[self.pending.pk], S.PENDING)
        arrived = PreOrder.objects.get(pk=self.old_big.pk)
        self.assertIsNotNone(arrived.arrived_at)
        event = arrived.events.get(to_status=S.ARRIVED)
        self.assertEqual(event.extra, {"arrival": {"received_quantity": 6}})

    def test_leftover_units_reported(self):
        result = self.arrive(10)
        self.assertEqual(result["units_left"], 4)

    def test_none_waiting(self):
        other = make_product()
        result = mark_product_arrived(
            product_id=other.pk, received_quantity=3, user=self.user
        )
        self.assertEqual(result, {"marked": [], "units_used": 0, "units_left": 3})

    def test_selected_orders(self):
        result = self.arrive(3, preorder_ids=[self.new_two.pk, self.mid_small.pk])
        self.assertEqual(
            [o.pk for o in result["marked"]], [self.mid_small.pk, self.new_two.pk]
        )
        self.assertEqual(self.statuses()[self.old_big.pk], S.ORDERED)

    def test_selected_orders_must_be_ordered_for_this_product(self):
        foreign = move(make_preorder(self.user, quantity=1), S.ORDERED)
        for ids in ([self.pending.pk], [foreign.pk], [999999]):
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                self.arrive(5, preorder_ids=ids)
        self.assertNotIn(S.ARRIVED, self.statuses().values())

    def test_selected_orders_must_fit(self):
        with self.assertRaises(ValidationError):
            self.arrive(3, preorder_ids=[self.old_big.pk, self.new_two.pk])
        self.assertNotIn(S.ARRIVED, self.statuses().values())

    def test_invalid_received_quantity(self):
        for value in (0, -1, None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.arrive(value)

    def test_stock_never_changes(self):
        self.arrive(6)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 4)
        self.assertFalse(InventoryMovement.objects.exists())


class PaymentTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.preorder = make_preorder(self.user)  # total 10000

    def pay(self, amount, **kwargs):
        values = {
            "preorder_id": self.preorder.pk,
            "user": self.user,
            "amount": D(amount),
            "payment_method": Payment.Method.CASH,
        }
        values.update(kwargs)
        return record_preorder_payment(**values)

    def refund(self, amount, reason="Adjust"):
        return self.pay(amount, payment_type=Payment.PaymentType.REFUND, reason=reason)

    def test_deposit_then_full(self):
        payment, _ = self.pay("4000.00")
        self.assertEqual(payment.preorder, self.preorder)
        self.pay("6000.00", payment_method=Payment.Method.GCASH)
        with self.assertRaises(ValidationError):
            self.pay("0.01")

    def test_over_balance_refused(self):
        self.pay("4000.00")
        with self.assertRaises(ValidationError):
            self.pay("7000.00")

    def test_invalid_amount_or_method(self):
        for amount, method in (("0", "CASH"), ("-5", "CASH"), ("10.00", "BITCOIN")):
            with self.subTest(amount=amount, method=method):
                with self.assertRaises(ValidationError):
                    self.pay(amount, payment_method=method)

    def test_receipt_refused_on_cancelled_and_fulfilled(self):
        cancel_preorder(preorder_id=self.preorder.pk, user=self.user, reason="x")
        with self.assertRaises(ValidationError):
            self.pay("10.00")

        fulfilled = make_preorder(self.user, quantity=1, agreed_unit_price=D("100.00"))
        make_payment(fulfilled, "100.00")
        move(fulfilled, S.ORDERED, S.ARRIVED)
        fulfill_preorder(preorder_id=fulfilled.pk, user=self.user)
        with self.assertRaises(ValidationError):
            record_preorder_payment(
                preorder_id=fulfilled.pk,
                user=self.user,
                amount=D("1.00"),
                payment_method=Payment.Method.CASH,
            )

    def test_refund_rules(self):
        self.pay("1000.00")
        with self.assertRaises(ValidationError):
            self.refund("10.00", reason=" ")
        with self.assertRaises(ValidationError):
            self.refund("1000.01")
        payment, _ = self.pay(
            "50.00",
            payment_type=Payment.PaymentType.REFUND,
            reason="Overcharge",
            notes="GCash ref 1",
        )
        self.assertEqual(payment.notes, "Overcharge — GCash ref 1")


class FulfillTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock_quantity=0)
        self.preorder = make_preorder(self.user, product=self.product)

    def fulfill(self):
        return fulfill_preorder(preorder_id=self.preorder.pk, user=self.user)

    def test_fulfill_paid_arrived_order(self):
        make_payment(self.preorder, "10000.00")
        move(self.preorder, S.ORDERED, S.ARRIVED)
        order = self.fulfill()
        self.assertEqual(order.status, S.FULFILLED)
        self.assertEqual(order.fulfilled_by, self.user)
        self.assertIsNotNone(order.fulfilled_at)
        self.assertTrue(
            order.events.filter(to_status=S.FULFILLED, from_status=S.ARRIVED).exists()
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_not_arrived_refused(self):
        make_payment(self.preorder, "10000.00")
        for statuses in ([], [S.ORDERED]):
            with self.subTest(statuses=statuses):
                move(self.preorder, *statuses)
                with self.assertRaises(ValidationError) as ctx:
                    self.fulfill()
                self.assertIn("not arrived", ctx.exception.messages[0])

    def test_balance_refused(self):
        make_payment(self.preorder, "4000.00")
        move(self.preorder, S.ORDERED, S.ARRIVED)
        with self.assertRaises(ValidationError) as ctx:
            self.fulfill()
        self.assertIn("6000.00", ctx.exception.messages[0])

    def test_final_refused(self):
        cancel_preorder(preorder_id=self.preorder.pk, user=self.user, reason="x")
        with self.assertRaises(ValidationError):
            self.fulfill()


class CancelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.preorder = make_preorder(self.user)

    def test_cancel_from_each_open_status(self):
        for path in ([], [S.ORDERED], [S.ORDERED, S.ARRIVED]):
            with self.subTest(path=path):
                order = move(make_preorder(self.user), *path)
                order = cancel_preorder(
                    preorder_id=order.pk,
                    user=self.user,
                    reason="  Supplier discontinued ",
                )
                self.assertEqual(order.status, S.CANCELLED)
                self.assertEqual(order.cancellation_reason, "Supplier discontinued")
                self.assertEqual(order.cancelled_by, self.user)
                event = order.events.get(event_type=E.CANCELLED)
                self.assertEqual(event.from_status, path[-1] if path else S.PENDING)

    def test_blank_reason_refused(self):
        for reason in ("", "  ", None):
            with self.subTest(reason=reason), self.assertRaises(ValidationError):
                cancel_preorder(
                    preorder_id=self.preorder.pk, user=self.user, reason=reason
                )

    def test_final_refused(self):
        cancel_preorder(preorder_id=self.preorder.pk, user=self.user, reason="x")
        with self.assertRaises(ValidationError):
            cancel_preorder(preorder_id=self.preorder.pk, user=self.user, reason="y")

    def test_payments_untouched_and_refund_allowed(self):
        make_payment(self.preorder, "4000.00")
        before = list(Payment.objects.values_list("pk", "amount", "status"))
        cancel_preorder(preorder_id=self.preorder.pk, user=self.user, reason="x")
        self.assertEqual(
            list(Payment.objects.values_list("pk", "amount", "status")), before
        )
        make_payment(self.preorder, "4000.00", payment_type=Payment.PaymentType.REFUND)
        with self.assertRaises(ValidationError):
            move(self.preorder, S.ORDERED)


class LegacyFulfilledTests(TestCase):
    """Pre-orders fulfilled before this feature without full payment (R2)."""

    def setUp(self):
        self.user = make_user()
        self.preorder = make_preorder(self.user)  # 10000
        make_payment(self.preorder, "4000.00")
        # The old admin could mark an unpaid pre-order fulfilled.
        PreOrder.objects.filter(pk=self.preorder.pk).update(
            status=S.FULFILLED,
            fulfilled_at=self.preorder.created_at,
            fulfilled_by=self.user,
        )
        self.preorder.refresh_from_db()

    def test_not_settled_until_paid_then_settled(self):
        self.assertFalse(self.preorder.is_settled)
        _, preorder = record_preorder_payment(
            preorder_id=self.preorder.pk,
            user=self.user,
            amount=D("6000.00"),
            payment_method=Payment.Method.CASH,
        )
        self.assertTrue(preorder.is_settled)
        with self.assertRaises(ValidationError):
            make_payment(preorder, "1.00")

    def test_normal_fulfillment_settles(self):
        order = make_preorder(self.user, quantity=1, agreed_unit_price=D("100.00"))
        make_payment(order, "100.00")
        move(order, S.ORDERED, S.ARRIVED)
        order = fulfill_preorder(preorder_id=order.pk, user=self.user)
        self.assertEqual(order.settled_at, order.fulfilled_at)
        make_payment(order, "30.00", payment_type=Payment.PaymentType.REFUND)
        self.assertTrue(order.is_settled)


class BackfillMigrationTests(TestCase):
    def test_only_paid_fulfilled_rows_are_settled(self):
        from importlib import import_module

        from django.apps import apps

        backfill = import_module("preorders.migrations.0004_backfill").backfill
        user = make_user()
        paid = make_preorder(user, quantity=1, agreed_unit_price=D("100.00"))
        make_payment(paid, "100.00")
        unpaid = make_preorder(user, quantity=1, agreed_unit_price=D("100.00"))
        PreOrder.objects.filter(pk__in=[paid.pk, unpaid.pk]).update(
            status=S.FULFILLED, fulfilled_at=paid.created_at, fulfilled_by=user
        )

        backfill(apps, None)

        paid.refresh_from_db()
        unpaid.refresh_from_db()
        self.assertIsNotNone(paid.settled_at)
        self.assertIsNone(unpaid.settled_at)
