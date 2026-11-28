"""Search (US4), audit history (US5) and the revenue report (US6)."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from sales.models import Payment
from stringing.models import StringingOrder
from stringing.selectors import order_history, revenue_report, search_orders
from stringing.services import (
    cancel_stringing_order,
    change_status,
    update_stringing_order,
)
from stringing.tests.factories import make_customer, make_order, make_payment, make_user

S = StringingOrder.Status
MANILA = ZoneInfo("Asia/Manila")


def D(value):
    return Decimal(value)


def set_times(order, **fields):
    StringingOrder.objects.filter(pk=order.pk).update(**fields)
    order.refresh_from_db()


class SearchOrdersTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.ana = make_customer(full_name="Ana Reyes", phone_number="0917 123 4567")
        self.ben = make_customer(full_name="Ben Cruz", phone_number="0918-555-0000")
        self.a1 = make_order(
            self.user,
            customer=self.ana,
            racket_description="Astrox 88D",
            string_type="BG80",
        )
        self.b1 = make_order(
            self.user,
            customer=self.ben,
            racket_description="Arcsaber 11",
            string_type="BG66 Ultimax",
        )
        self.walk_in = make_order(
            self.user, racket_description="Victor Thruster", string_type="VBS-63"
        )

    def ids(self, **params):
        return set(search_orders(params).values_list("pk", flat=True))

    def test_search_by_order_number(self):
        self.assertEqual(self.ids(search=self.b1.order_number[-4:]), {self.b1.pk})

    def test_search_by_customer_name_case_insensitive(self):
        self.assertEqual(self.ids(search="ana re"), {self.a1.pk})

    def test_search_by_phone_any_format(self):
        for query in ("09171234567", "+63 917 123 4567", "4567", "0917-123"):
            with self.subTest(query=query):
                self.assertEqual(self.ids(search=query), {self.a1.pk})

    def test_search_by_racket_and_string(self):
        self.assertEqual(self.ids(search="arcsaber"), {self.b1.pk})
        self.assertEqual(self.ids(search="bg80"), {self.a1.pk})

    def test_walk_in_found_by_number_racket_and_string(self):
        for query in (self.walk_in.order_number, "thruster", "vbs"):
            with self.subTest(query=query):
                self.assertEqual(self.ids(search=query), {self.walk_in.pk})

    def test_empty_search_returns_all(self):
        self.assertEqual(len(self.ids(search="  ")), 3)

    def test_multi_status_filter(self):
        change_status(order_id=self.a1.pk, user=self.user, to_status=S.IN_PROGRESS)
        cancel_stringing_order(order_id=self.b1.pk, user=self.user, reason="x", materials_used=False)
        self.assertEqual(self.ids(status="IN_PROGRESS"), {self.a1.pk})
        self.assertEqual(
            self.ids(status="in_progress,CANCELLED"), {self.a1.pk, self.b1.pk}
        )

    def test_payment_state_filter(self):
        make_payment(self.a1, "100.00")
        make_payment(self.b1, "400.00")
        self.assertEqual(self.ids(payment_state="PARTIAL"), {self.a1.pk})
        self.assertEqual(self.ids(payment_state="paid"), {self.b1.pk})
        self.assertEqual(self.ids(payment_state="UNPAID"), {self.walk_in.pk})

    def test_payment_state_filter_excludes_cancelled(self):
        make_payment(self.a1, "100.00")
        cancel_stringing_order(order_id=self.a1.pk, user=self.user, reason="x", materials_used=False)
        self.assertEqual(self.ids(payment_state="PARTIAL"), set())
        self.assertEqual(
            self.ids(payment_state="UNPAID"), {self.b1.pk, self.walk_in.pk}
        )

    def test_customer_filter(self):
        self.assertEqual(self.ids(customer=str(self.ben.pk)), {self.b1.pk})

    def test_date_range_is_store_local_and_inclusive(self):
        # 2026-11-01 23:30 Manila is 15:30 UTC the same day.
        set_times(self.a1, created_at=datetime(2026, 11, 1, 23, 30, tzinfo=MANILA))
        # 2026-11-02 00:30 Manila is still 2026-11-01 in UTC.
        set_times(self.b1, created_at=datetime(2026, 11, 2, 0, 30, tzinfo=MANILA))
        set_times(self.walk_in, created_at=datetime(2026, 11, 3, 12, 0, tzinfo=MANILA))
        self.assertEqual(
            self.ids(received_from="2026-11-01", received_to="2026-11-01"), {self.a1.pk}
        )
        self.assertEqual(
            self.ids(received_from="2026-11-02", received_to="2026-11-03"),
            {self.b1.pk, self.walk_in.pk},
        )

    def test_orderings(self):
        default = list(search_orders({}).values_list("pk", flat=True))
        self.assertEqual(default, [self.walk_in.pk, self.b1.pk, self.a1.pk])
        oldest = list(
            search_orders({"ordering": "created_at"}).values_list("pk", flat=True)
        )
        self.assertEqual(oldest, [self.a1.pk, self.b1.pk, self.walk_in.pk])
        change_status(order_id=self.walk_in.pk, user=self.user, to_status=S.IN_PROGRESS)
        by_status = list(
            search_orders({"ordering": "status"}).values_list("pk", flat=True)
        )
        self.assertEqual(by_status[0], self.walk_in.pk)

    def test_invalid_values_rejected(self):
        cases = {
            "status": "DONE",
            "payment_state": "SOME",
            "customer": "abc",
            "received_from": "2026-13-01",
            "ordering": "price",
        }
        for param, value in cases.items():
            with self.subTest(param=param), self.assertRaises(ValidationError) as ctx:
                search_orders({param: value})
            self.assertIn(param, ctx.exception.message_dict)

    def test_non_ascii_digit_customer_rejected(self):
        for value in ("²", "①", "٣"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                search_orders({"customer": value})

    def test_reversed_date_range_rejected(self):
        with self.assertRaises(ValidationError):
            search_orders({"received_from": "2026-11-05", "received_to": "2026-11-01"})


class OrderHistoryTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)

    def test_events_and_payments_merged_in_time_order(self):
        change_status(order_id=self.order.pk, user=self.user, to_status=S.IN_PROGRESS)
        make_payment(self.order, "100.00")
        update_stringing_order(
            order_id=self.order.pk, user=self.user, discount_amount=D("60.00")
        )
        cancel_stringing_order(order_id=self.order.pk, user=self.user, reason="Gone", materials_used=False)

        history = order_history(self.order, can_view_financials=True)
        self.assertEqual(
            [entry["type"] for entry in history],
            ["CREATED", "STATUS_CHANGED", "PAYMENT", "UPDATED", "CANCELLED"],
        )
        self.assertEqual(history[2]["amount"], "100.00")
        self.assertEqual(history[2]["payment_type"], Payment.PaymentType.RECEIPT)
        self.assertEqual(history[3]["changes"], {"discount_amount": ["50.00", "60.00"]})
        self.assertEqual(history[4]["reason"], "Gone")
        self.assertEqual(history[4]["from_status"], S.IN_PROGRESS)

    def test_payment_entry_uses_payment_date(self):
        payment = make_payment(self.order, "100.00")
        backdated = datetime(2026, 1, 5, 9, 0, tzinfo=MANILA)
        Payment.objects.filter(pk=payment.pk).update(payment_date=backdated)
        history = order_history(self.order, can_view_financials=True)
        self.assertEqual([e["type"] for e in history], ["PAYMENT", "CREATED"])
        self.assertEqual(history[0]["at"], backdated)

    def test_direct_cost_changes_masked_without_permission(self):
        update_stringing_order(
            order_id=self.order.pk,
            user=self.user,
            direct_cost=D("200.00"),
            tension="24 lbs",
        )
        update_stringing_order(
            order_id=self.order.pk, user=self.user, direct_cost=D("210.00")
        )
        history = order_history(self.order, can_view_financials=False)
        updates = [entry for entry in history if entry["type"] == "UPDATED"]
        self.assertEqual(updates, [updates[0]])
        self.assertEqual(updates[0]["changes"], {"tension": ["26 lbs", "24 lbs"]})

        full = order_history(self.order, can_view_financials=True)
        self.assertEqual(len([e for e in full if e["type"] == "UPDATED"]), 2)


class RevenueReportTests(TestCase):
    DAY = date(2026, 11, 10)

    def setUp(self):
        self.user = make_user()

    def at(self, day, hour=12, minute=0):
        return datetime(2026, 11, day, hour, minute, tzinfo=MANILA)

    def paid_order(self, paid_at, **overrides):
        order = make_order(self.user, **overrides)
        make_payment(order, f"{order.total_amount:.2f}")
        set_times(order, paid_in_full_at=paid_at, created_at=paid_at)
        return order

    def report(self, start=None, end=None):
        return revenue_report(start or self.DAY, end or self.DAY)

    def test_add_ons_count_toward_revenue(self):
        # 450 service + 50 stencil + 120 grip - 50 discount = 570.
        self.paid_order(
            self.at(10),
            has_stencil=True,
            stencil_price=D("50.00"),
            has_grip=True,
            grip_price=D("120.00"),
        )
        report = self.report()
        self.assertEqual(report["gross_service_price"], D("450.00"))
        self.assertEqual(report["gross_add_ons"], D("170.00"))
        self.assertEqual(report["net_revenue"], D("570.00"))
        self.assertEqual(report["profit"], D("390.00"))

    def test_counts_only_paid_in_full_non_cancelled(self):
        # Paid in full: 400 revenue (450 - 50), 180 cost.
        self.paid_order(self.at(10))
        # Paid in full: 300 revenue, 0 cost.
        self.paid_order(
            self.at(10, 18),
            service_price=D("300.00"),
            discount_amount=D("0.00"),
            direct_cost=D("0.00"),
        )
        # Partially paid: not counted.
        partial = make_order(self.user)
        make_payment(partial, "100.00")
        set_times(partial, created_at=self.at(10))
        # Paid in full, then cancelled: not counted.
        cancelled = self.paid_order(self.at(10))
        cancel_stringing_order(order_id=cancelled.pk, user=self.user, reason="x", materials_used=False)
        set_times(cancelled, cancelled_at=self.at(10, 15))

        report = self.report()
        self.assertEqual(report["orders_count"], 2)
        self.assertEqual(report["gross_service_price"], D("750.00"))
        self.assertEqual(report["total_discounts"], D("50.00"))
        self.assertEqual(report["net_revenue"], D("700.00"))
        self.assertEqual(report["total_direct_cost"], D("180.00"))
        self.assertEqual(report["profit"], D("520.00"))
        self.assertEqual(report["cancelled_count"], 1)
        self.assertEqual(report["unpaid_count"], 1)
        self.assertEqual(report["outstanding_balance"], D("300.00"))

    def test_store_local_day_boundaries(self):
        self.paid_order(self.at(10, 23, 30))  # 15:30 UTC on the 10th
        self.paid_order(
            self.at(11, 0, 30)
        )  # 16:30 UTC on the 10th, but the 11th locally
        self.assertEqual(self.report()["orders_count"], 1)
        self.assertEqual(
            self.report(date(2026, 11, 11), date(2026, 11, 11))["orders_count"], 1
        )

    def test_empty_range_returns_zeros(self):
        report = self.report()
        self.assertEqual(report["orders_count"], 0)
        self.assertEqual(report["net_revenue"], D("0.00"))
        self.assertEqual(report["profit"], D("0.00"))
        self.assertEqual(report["outstanding_balance"], D("0.00"))

    def test_reversed_range_rejected(self):
        with self.assertRaises(ValidationError):
            revenue_report(date(2026, 11, 2), date(2026, 11, 1))

    def test_refunds_after_pickup_reported_separately(self):
        # Recognized on the 10th, picked up on the 10th, refund 10.00 on the 12th.
        order = self.paid_order(self.at(10))
        for status in (S.IN_PROGRESS, S.READY, S.COMPLETED):
            change_status(order_id=order.pk, user=self.user, to_status=status)
        set_times(order, completed_at=self.at(10, 13))
        refund = make_payment(order, "10.00", payment_type=Payment.PaymentType.REFUND)
        Payment.objects.filter(pk=refund.pk).update(payment_date=self.at(12))

        recognized = self.report()
        self.assertEqual(recognized["net_revenue"], D("400.00"))
        self.assertEqual(recognized["total_refunds"], D("0.00"))
        self.assertEqual(recognized["unpaid_count"], 0)

        refunded = self.report(date(2026, 11, 12), date(2026, 11, 12))
        self.assertEqual(refunded["orders_count"], 0)
        self.assertEqual(refunded["total_refunds"], D("10.00"))
        self.assertEqual(refunded["net_revenue_after_refunds"], D("-10.00"))
        self.assertEqual(refunded["profit_after_refunds"], D("-10.00"))

        whole = self.report(date(2026, 11, 1), date(2026, 11, 30))
        self.assertEqual(whole["net_revenue_after_refunds"], D("390.00"))
        self.assertEqual(whole["profit_after_refunds"], D("210.00"))

    def test_refunds_before_pickup_not_counted_separately(self):
        order = make_order(self.user)
        make_payment(order, "400.00")
        make_payment(order, "50.00", payment_type=Payment.PaymentType.REFUND)
        make_payment(order, "50.00")
        for status in (S.IN_PROGRESS, S.READY, S.COMPLETED):
            change_status(order_id=order.pk, user=self.user, to_status=status)
        today = order.created_at.astimezone(MANILA).date()
        report = revenue_report(today, today)
        self.assertEqual(report["net_revenue"], D("400.00"))
        self.assertEqual(report["total_refunds"], D("0.00"))

    def test_legacy_unpaid_completed_order_counts_as_unpaid(self):
        order = make_order(self.user)
        set_times(
            order, status=S.COMPLETED, completed_at=self.at(10), created_at=self.at(10)
        )
        report = self.report()
        self.assertEqual(report["orders_count"], 0)
        self.assertEqual(report["unpaid_count"], 1)
        self.assertEqual(report["outstanding_balance"], D("400.00"))

    def test_uses_three_queries(self):
        self.paid_order(self.at(10))
        with CaptureQueriesContext(connection) as ctx:
            self.report()
        self.assertEqual(len(ctx.captured_queries), 3)
