"""Service rules for stringing orders (US1, US2, US3, US5)."""

import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from sales.models import Payment
from stringing.models import StringingOrder, StringingOrderEvent
from stringing.services import (
    StatusConflict,
    cancel_stringing_order,
    change_status,
    create_stringing_order,
    record_order_payment,
    update_stringing_order,
)
from stringing.tests.factories import (
    make_customer,
    make_order,
    make_payment,
    make_user,
)

S = StringingOrder.Status
E = StringingOrderEvent.EventType


def D(value):
    return Decimal(value)


class CreateOrderTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def create(self, **overrides):
        values = {
            "user": self.user,
            "racket_description": "Yonex Astrox 88D, 4U",
            "string_type": "BG80",
            "tension": "26 lbs",
            "service_price": D("450.00"),
            "discount_amount": D("50.00"),
            "direct_cost": D("180.00"),
        }
        values.update(overrides)
        return create_stringing_order(**values)

    def test_creates_received_order_for_customer(self):
        customer = make_customer()
        order = self.create(customer=customer)
        self.assertEqual(order.status, S.RECEIVED)
        self.assertEqual(order.customer, customer)
        self.assertEqual(order.total_amount, D("400.00"))
        self.assertEqual(order.created_by, self.user)
        self.assertIsNone(order.paid_in_full_at)

    def test_walk_in_order(self):
        self.assertIsNone(self.create().customer)

    def test_order_number_format_and_increment(self):
        first, second = self.create(), self.create()
        pattern = re.compile(r"^STR-\d{4}-(\d{6})$")
        a, b = pattern.match(first.order_number), pattern.match(second.order_number)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual(int(b.group(1)), int(a.group(1)) + 1)

    def test_text_is_trimmed(self):
        order = self.create(racket_description="  Astrox  ", tension=" 24 lbs ")
        self.assertEqual(order.racket_description, "Astrox")
        self.assertEqual(order.tension, "24 lbs")

    def assert_field_error(self, field, **overrides):
        with self.assertRaises(ValidationError) as ctx:
            self.create(**overrides)
        self.assertIn(field, ctx.exception.message_dict)
        self.assertEqual(StringingOrder.objects.count(), 0)

    def test_blank_racket_rejected(self):
        self.assert_field_error("racket_description", racket_description="  ")

    def test_blank_string_rejected(self):
        self.assert_field_error("string_type", string_type="")

    def test_negative_price_rejected(self):
        self.assert_field_error(
            "service_price", service_price=D("-1"), discount_amount=D("0")
        )

    def test_negative_discount_rejected(self):
        self.assert_field_error("discount_amount", discount_amount=D("-1"))

    def test_discount_above_price_rejected(self):
        self.assert_field_error("discount_amount", discount_amount=D("450.01"))

    def test_negative_cost_rejected(self):
        self.assert_field_error("direct_cost", direct_cost=D("-1"))

    def test_archived_customer_rejected(self):
        self.assert_field_error("customer", customer=make_customer(is_active=False))

    def test_created_event_written(self):
        order = self.create()
        event = order.events.get()
        self.assertEqual(event.event_type, E.CREATED)
        self.assertEqual(event.performed_by, self.user)

    def test_zero_total_order_is_paid_in_full(self):
        order = self.create(discount_amount=D("450.00"))
        self.assertIsNotNone(order.paid_in_full_at)


class UpdateOrderTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)  # 450 - 50 = 400

    def update(self, **changes):
        return update_stringing_order(order_id=self.order.pk, user=self.user, **changes)

    def test_changes_recorded_with_old_and_new_values(self):
        self.update(discount_amount=D("100.00"), tension="24 lbs")
        event = self.order.events.get(event_type=E.UPDATED)
        self.assertEqual(
            event.changes,
            {"discount_amount": ["50.00", "100.00"], "tension": ["26 lbs", "24 lbs"]},
        )

    def test_no_change_writes_no_event(self):
        self.update(tension="26 lbs")
        self.assertFalse(self.order.events.filter(event_type=E.UPDATED).exists())

    def test_same_validation_as_create(self):
        with self.assertRaises(ValidationError) as ctx:
            self.update(discount_amount=D("500.00"))
        self.assertIn("discount_amount", ctx.exception.message_dict)

    def test_customer_change_to_archived_rejected(self):
        with self.assertRaises(ValidationError):
            self.update(customer=make_customer(is_active=False))

    def test_refused_when_completed(self):
        make_payment(self.order, "400.00")
        for status in (S.IN_PROGRESS, S.READY, S.COMPLETED):
            change_status(order_id=self.order.pk, user=self.user, to_status=status)
        with self.assertRaises(ValidationError):
            self.update(tension="20 lbs")

    def test_refused_when_cancelled(self):
        cancel_stringing_order(order_id=self.order.pk, user=self.user, reason="x")
        with self.assertRaises(ValidationError):
            self.update(tension="20 lbs")

    def test_total_below_paid_rejected(self):
        make_payment(self.order, "300.00")
        with self.assertRaises(ValidationError):
            self.update(discount_amount=D("200.00"))  # total 250 < 300

    def test_discount_making_order_fully_paid_sets_paid_in_full(self):
        make_payment(self.order, "350.00")
        order = self.update(discount_amount=D("100.00"))  # total 350
        self.assertIsNotNone(order.paid_in_full_at)

    def test_price_increase_clears_paid_in_full(self):
        make_payment(self.order, "400.00")
        self.assertIsNotNone(self.order.paid_in_full_at)
        order = self.update(service_price=D("500.00"))
        self.assertIsNone(order.paid_in_full_at)

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValidationError):
            self.update(order_number="X")


class ChangeStatusTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)

    def move(self, to_status, **kwargs):
        return change_status(
            order_id=self.order.pk, user=self.user, to_status=to_status, **kwargs
        )

    def test_forward_path_with_timestamps_and_events(self):
        self.move(S.IN_PROGRESS)
        order = self.move(S.READY)
        self.assertIsNotNone(order.ready_at)
        make_payment(self.order, "400.00")
        order = self.move(S.COMPLETED)
        self.assertEqual(order.status, S.COMPLETED)
        self.assertIsNotNone(order.completed_at)
        transitions = list(
            self.order.events.filter(event_type=E.STATUS_CHANGED).values_list(
                "from_status", "to_status"
            )
        )
        self.assertEqual(
            transitions,
            [
                (S.RECEIVED, S.IN_PROGRESS),
                (S.IN_PROGRESS, S.READY),
                (S.READY, S.COMPLETED),
            ],
        )

    def test_step_backs_allowed(self):
        self.move(S.IN_PROGRESS)
        self.move(S.RECEIVED)
        self.move(S.IN_PROGRESS)
        self.move(S.READY)
        order = self.move(S.IN_PROGRESS)
        self.assertIsNone(order.ready_at)

    def test_skips_refused(self):
        for target in (S.READY, S.COMPLETED):
            with self.subTest(target=target), self.assertRaises(ValidationError):
                self.move(target)
        self.move(S.IN_PROGRESS)
        with self.assertRaises(ValidationError):
            self.move(S.COMPLETED)

    def test_message_names_allowed_statuses(self):
        with self.assertRaises(ValidationError) as ctx:
            self.move(S.COMPLETED)
        self.assertIn("In Progress", ctx.exception.messages[0])

    def test_cancel_via_status_refused(self):
        with self.assertRaises(ValidationError):
            self.move(S.CANCELLED)

    def test_complete_with_balance_refused(self):
        self.move(S.IN_PROGRESS)
        self.move(S.READY)
        make_payment(self.order, "150.00")
        with self.assertRaises(ValidationError) as ctx:
            self.move(S.COMPLETED)
        self.assertIn("250.00", ctx.exception.messages[0])

    def test_completed_is_final(self):
        make_payment(self.order, "400.00")
        for status in (S.IN_PROGRESS, S.READY, S.COMPLETED):
            self.move(status)
        with self.assertRaises(ValidationError):
            self.move(S.READY)

    def test_cancelled_is_final(self):
        cancel_stringing_order(order_id=self.order.pk, user=self.user, reason="x")
        with self.assertRaises(ValidationError):
            self.move(S.IN_PROGRESS)

    def test_stale_expected_status_refused(self):
        self.move(S.IN_PROGRESS)
        with self.assertRaises(StatusConflict) as ctx:
            self.move(S.READY, expected_status=S.RECEIVED)
        self.assertEqual(ctx.exception.current_status, S.IN_PROGRESS)

    def test_matching_expected_status_allowed(self):
        order = self.move(S.IN_PROGRESS, expected_status=S.RECEIVED)
        self.assertEqual(order.status, S.IN_PROGRESS)


class PaymentTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)  # total 400

    def pay(self, amount, **kwargs):
        values = {
            "order_id": self.order.pk,
            "user": self.user,
            "amount": D(amount),
            "payment_method": Payment.Method.CASH,
        }
        values.update(kwargs)
        return record_order_payment(**values)

    def refund(self, amount, reason="Overpaid"):
        return self.pay(amount, payment_type=Payment.PaymentType.REFUND, reason=reason)

    def test_partial_then_full(self):
        _, order = self.pay("150.00")
        self.assertIsNone(order.paid_in_full_at)
        payment, order = self.pay("250.00", payment_method=Payment.Method.GCASH)
        self.assertEqual(payment.received_by, self.user)
        self.assertIsNotNone(order.paid_in_full_at)

    def test_over_balance_refused(self):
        self.pay("150.00")
        with self.assertRaises(ValidationError):
            self.pay("300.00")

    def test_non_positive_amount_refused(self):
        for amount in ("0", "-5"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.pay(amount)

    def test_unknown_method_refused(self):
        with self.assertRaises(ValidationError):
            self.pay("10.00", payment_method="BITCOIN")

    def test_receipt_on_cancelled_refused(self):
        cancel_stringing_order(order_id=self.order.pk, user=self.user, reason="x")
        with self.assertRaises(ValidationError):
            self.pay("10.00")

    def test_refund_requires_reason(self):
        self.pay("100.00")
        with self.assertRaises(ValidationError):
            self.refund("50.00", reason="  ")

    def test_refund_above_paid_refused(self):
        self.pay("100.00")
        with self.assertRaises(ValidationError):
            self.refund("100.01")

    def test_refund_after_pickup_keeps_order_settled(self):
        self.pay("400.00")
        for status in (S.IN_PROGRESS, S.READY, S.COMPLETED):
            change_status(order_id=self.order.pk, user=self.user, to_status=status)
        self.order.refresh_from_db()
        paid_at = self.order.paid_in_full_at
        _, order = self.refund("10.00", reason="Goodwill")
        self.assertEqual(order.status, S.COMPLETED)
        self.assertEqual(order.paid_in_full_at, paid_at)

    def test_receipt_on_settled_order_refused(self):
        self.pay("400.00")
        for status in (S.IN_PROGRESS, S.READY, S.COMPLETED):
            change_status(order_id=self.order.pk, user=self.user, to_status=status)
        self.refund("100.00")
        with self.assertRaises(ValidationError):
            self.pay("100.00")

    def test_legacy_unpaid_completed_order_can_be_collected(self):
        # Before this feature, orders could be completed without payment.
        StringingOrder.objects.filter(pk=self.order.pk).update(
            status=S.COMPLETED, completed_at=self.order.created_at
        )
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_settled)
        _, order = self.pay("400.00")
        self.assertTrue(order.is_settled)
        self.assertIsNotNone(order.paid_in_full_at)

    def test_refund_keeps_extra_notes(self):
        self.pay("100.00")
        payment, _ = self.pay(
            "50.00",
            payment_type=Payment.PaymentType.REFUND,
            reason="Overcharge",
            notes="GCash ref 123",
        )
        self.assertEqual(payment.notes, "Overcharge — GCash ref 123")

    def test_refund_clears_paid_in_full(self):
        self.pay("400.00")
        _, order = self.refund("50.00")
        self.assertIsNone(order.paid_in_full_at)
        _, order = self.pay("50.00")
        self.assertIsNotNone(order.paid_in_full_at)


class CancelOrderTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)

    def cancel(self, reason="Customer changed mind"):
        return cancel_stringing_order(
            order_id=self.order.pk, user=self.user, reason=reason
        )

    def test_cancel_from_each_open_status(self):
        for path in ([], [S.IN_PROGRESS], [S.IN_PROGRESS, S.READY]):
            with self.subTest(path=path):
                order = make_order(self.user)
                for status in path:
                    change_status(order_id=order.pk, user=self.user, to_status=status)
                order = cancel_stringing_order(
                    order_id=order.pk, user=self.user, reason="  Changed mind "
                )
                self.assertEqual(order.status, S.CANCELLED)
                self.assertEqual(order.cancellation_reason, "Changed mind")
                self.assertEqual(order.cancelled_by, self.user)
                self.assertIsNotNone(order.cancelled_at)
                event = order.events.get(event_type=E.CANCELLED)
                self.assertEqual(event.from_status, path[-1] if path else S.RECEIVED)
                self.assertEqual(event.reason, "Changed mind")

    def test_blank_reason_refused(self):
        for reason in ("", "   ", None):
            with self.subTest(reason=reason), self.assertRaises(ValidationError):
                self.cancel(reason)

    def test_final_orders_refused(self):
        self.cancel()
        with self.assertRaises(ValidationError):
            self.cancel()
        done = make_order(self.user, discount_amount=D("450.00"))
        for status in (S.IN_PROGRESS, S.READY, S.COMPLETED):
            change_status(order_id=done.pk, user=self.user, to_status=status)
        with self.assertRaises(ValidationError):
            cancel_stringing_order(order_id=done.pk, user=self.user, reason="x")

    def test_payments_untouched_and_refund_allowed(self):
        make_payment(self.order, "400.00")
        before = list(Payment.objects.values_list("pk", "amount", "status"))
        order = self.cancel()
        self.assertEqual(
            list(Payment.objects.values_list("pk", "amount", "status")), before
        )
        self.assertIsNone(order.paid_in_full_at)
        make_payment(self.order, "400.00", payment_type=Payment.PaymentType.REFUND)
        self.assertIsNone(self.order.paid_in_full_at)
