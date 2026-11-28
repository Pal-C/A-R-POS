"""API tests for /api/stringing/ (contracts/stringing-api.md)."""

from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from sales.models import Payment
from stringing.models import StringingOrder
from stringing.services import cancel_stringing_order, change_status
from stringing.tests.factories import (
    ALL_PERMISSIONS,
    make_customer,
    make_order,
    make_payment,
    make_user,
)

S = StringingOrder.Status
LIST_URL = reverse("stringing-order-list-create")


def url(name, order):
    return reverse(name, kwargs={"pk": order.pk if hasattr(order, "pk") else order})


class StringingAPITestCase(APITestCase):
    def setUp(self):
        self.manager = make_user(perms=ALL_PERMISSIONS)
        self.staff = make_user()
        self.customer = make_customer(full_name="Ana Reyes", phone_number="09171234567")
        self.client.force_authenticate(self.manager)

    def as_user(self, user):
        self.client.force_authenticate(user)


class CreateDetailEditAPITests(StringingAPITestCase):
    payload = {
        "racket_description": "Yonex Astrox 88D, 4U",
        "string_type": "BG80",
        "tension": "26 lbs",
        "service_price": "450.00",
        "discount_amount": "50.00",
        "direct_cost": "180.00",
    }

    def test_create_returns_detail(self):
        response = self.client.post(
            LIST_URL, {**self.payload, "customer": self.customer.pk}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        self.assertRegex(data["order_number"], r"^STR-\d{4}-\d{6}$")
        self.assertEqual(data["status"], S.RECEIVED)
        self.assertEqual(data["status_display"], "Received")
        self.assertEqual(data["total_amount"], "400.00")
        self.assertEqual(data["amount_paid"], "0.00")
        self.assertEqual(data["balance"], "400.00")
        self.assertEqual(data["payment_state"], "UNPAID")
        self.assertEqual(data["direct_cost"], "180.00")
        self.assertEqual(data["profit"], "220.00")
        self.assertEqual(data["customer"]["full_name"], "Ana Reyes")
        self.assertEqual(data["created_by"]["id"], self.manager.pk)
        self.assertEqual(data["notes"], "")

    def test_create_walk_in(self):
        response = self.client.post(LIST_URL, self.payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["customer"])

    def test_create_field_errors(self):
        cases = {
            "racket_description": {"racket_description": ""},
            "string_type": {"string_type": "   "},
            "service_price": {"service_price": "-1.00"},
            "discount_amount": {"discount_amount": "500.00"},
            "direct_cost": {"direct_cost": "-1"},
            "customer": {"customer": make_customer(is_active=False).pk},
        }
        for field, override in cases.items():
            with self.subTest(field=field):
                response = self.client.post(
                    LIST_URL, {**self.payload, **override}, format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        self.assertEqual(StringingOrder.objects.count(), 0)

    def test_missing_required_fields(self):
        response = self.client.post(LIST_URL, {}, format="json")
        self.assertEqual(response.status_code, 400)
        for field in ("racket_description", "string_type", "service_price"):
            self.assertIn(field, response.data)

    def test_financials_hidden_without_permission(self):
        self.as_user(self.staff)
        response = self.client.post(LIST_URL, self.payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("direct_cost", response.data)
        self.assertNotIn("profit", response.data)
        # Cost entered at intake is still stored.
        order = StringingOrder.objects.get(pk=response.data["id"])
        self.assertEqual(order.direct_cost, Decimal("180.00"))

        listing = self.client.get(LIST_URL)
        self.assertNotIn("direct_cost", listing.data["results"][0])

    def test_detail_404(self):
        self.assertEqual(
            self.client.get(url("stringing-order-detail", 999999)).status_code, 404
        )

    def test_delete_not_allowed(self):
        order = make_order(self.manager)
        response = self.client.delete(url("stringing-order-detail", order))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(StringingOrder.objects.filter(pk=order.pk).exists())

    def test_patch(self):
        order = make_order(self.manager)
        response = self.client.patch(
            url("stringing-order-detail", order),
            {"tension": "24 lbs", "notes": "Pre-stretch"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["tension"], "24 lbs")
        self.assertEqual(response.data["notes"], "Pre-stretch")

    def test_patch_total_below_paid(self):
        order = make_order(self.manager)
        make_payment(order, "300.00")
        response = self.client.patch(
            url("stringing-order-detail", order),
            {"discount_amount": "200.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("300.00", str(response.data))

    def test_patch_final_order_refused(self):
        order = make_order(self.manager)
        cancel_stringing_order(order_id=order.pk, user=self.manager, reason="x", materials_used=False)
        response = self.client.patch(
            url("stringing-order-detail", order), {"tension": "1"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_direct_cost_requires_permission(self):
        order = make_order(self.manager)
        self.as_user(self.staff)
        response = self.client.patch(
            url("stringing-order-detail", order), {"direct_cost": "1.00"}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.direct_cost, Decimal("180.00"))

    def test_patch_404(self):
        response = self.client.patch(
            url("stringing-order-detail", 999999), {"tension": "1"}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_detail_query_count(self):
        order = make_order(self.manager, customer=self.customer)
        make_payment(order, "100.00")
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url("stringing-order-detail", order))
        self.assertEqual(response.status_code, 200)
        # Order (with customer, users and net paid subquery) plus permission
        # lookups for financial masking.
        self.assertLessEqual(len(ctx.captured_queries), 3)


class StatusAPITests(StringingAPITestCase):
    def setUp(self):
        super().setUp()
        self.order = make_order(self.manager)

    def post(self, data):
        return self.client.post(
            url("stringing-order-status", self.order), data, format="json"
        )

    def test_change_status(self):
        response = self.post({"status": S.IN_PROGRESS})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], S.IN_PROGRESS)

    def test_invalid_transition_names_allowed(self):
        response = self.post({"status": S.COMPLETED})
        self.assertEqual(response.status_code, 400)
        self.assertIn("In Progress", str(response.data))

    def test_complete_with_balance(self):
        change_status(
            order_id=self.order.pk, user=self.manager, to_status=S.IN_PROGRESS
        )
        change_status(order_id=self.order.pk, user=self.manager, to_status=S.READY)
        response = self.post({"status": S.COMPLETED})
        self.assertEqual(response.status_code, 400)
        self.assertIn("400.00", str(response.data))

    def test_stale_expected_status(self):
        change_status(
            order_id=self.order.pk, user=self.manager, to_status=S.IN_PROGRESS
        )
        response = self.post({"status": S.READY, "expected_status": S.RECEIVED})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["current_status"], S.IN_PROGRESS)
        self.assertIn("detail", response.data)

    def test_unknown_status(self):
        self.assertEqual(self.post({"status": "DONE"}).status_code, 400)

    def test_404(self):
        response = self.client.post(
            url("stringing-order-status", 999999),
            {"status": S.IN_PROGRESS},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class PaymentAPITests(StringingAPITestCase):
    def setUp(self):
        super().setUp()
        self.order = make_order(self.manager)  # total 400
        self.url = url("stringing-order-payments", self.order)

    def post(self, data):
        return self.client.post(self.url, data, format="json")

    def receipt(self, amount):
        return self.post({"amount": amount, "payment_method": Payment.Method.CASH})

    def test_partial_then_full(self):
        response = self.receipt("150.00")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["payment"]["amount"], "150.00")
        self.assertEqual(response.data["payment"]["received_by"]["id"], self.manager.pk)
        self.assertEqual(response.data["order"]["balance"], "250.00")
        self.assertEqual(response.data["order"]["payment_state"], "PARTIAL")

        response = self.receipt("250.00")
        self.assertEqual(response.data["order"]["payment_state"], "PAID")
        self.assertIsNotNone(response.data["order"]["paid_in_full_at"])

    def test_validation_errors(self):
        self.receipt("150.00")
        for data in (
            {"amount": "300.00", "payment_method": "CASH"},
            {"amount": "0", "payment_method": "CASH"},
            {"amount": "10.00"},
            {"amount": "10.00", "payment_method": "BITCOIN"},
            {"amount": "10.00", "payment_method": "CASH", "payment_type": "REFUND"},
        ):
            with self.subTest(data=data):
                self.assertEqual(self.post(data).status_code, 400)

    def test_receipt_on_cancelled_refused_refund_allowed(self):
        self.receipt("100.00")
        cancel_stringing_order(order_id=self.order.pk, user=self.manager, reason="x", materials_used=False)
        detail = self.client.get(url("stringing-order-detail", self.order)).data
        self.assertEqual(detail["refund_due"], "100.00")
        self.assertEqual(detail["balance"], "0.00")
        self.assertEqual(self.receipt("10.00").status_code, 400)

        response = self.post(
            {
                "amount": "100.00",
                "payment_method": "CASH",
                "payment_type": "REFUND",
                "reason": "Cancelled order",
            }
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["payment"]["notes"], "Cancelled order")
        self.assertEqual(response.data["order"]["refund_due"], "0.00")

    def test_receipt_requires_permission(self):
        self.as_user(self.staff)
        self.assertEqual(self.receipt("10.00").status_code, 403)

    def test_refund_requires_permission(self):
        make_payment(self.order, "100.00")
        self.as_user(make_user(perms=["sales.record_payment"]))
        response = self.post(
            {
                "amount": "10",
                "payment_method": "CASH",
                "payment_type": "REFUND",
                "reason": "r",
            }
        )
        self.assertEqual(response.status_code, 403)

    def test_completed_order_stays_paid_after_refund(self):
        make_payment(self.order, "400.00")
        for status in (S.IN_PROGRESS, S.READY, S.COMPLETED):
            change_status(order_id=self.order.pk, user=self.manager, to_status=status)
        response = self.post(
            {
                "amount": "10.00",
                "payment_method": "CASH",
                "payment_type": "REFUND",
                "reason": "Goodwill",
            }
        )
        self.assertEqual(response.status_code, 201, response.data)
        order = response.data["order"]
        self.assertEqual(order["amount_paid"], "390.00")
        self.assertEqual(order["balance"], "0.00")
        self.assertEqual(order["payment_state"], "PAID")

        listing = self.client.get(LIST_URL, {"payment_state": "PAID"})
        self.assertEqual([o["id"] for o in listing.data["results"]], [self.order.pk])

    def test_legacy_unpaid_completed_order_shows_real_balance(self):
        StringingOrder.objects.filter(pk=self.order.pk).update(
            status=S.COMPLETED, completed_at=self.order.created_at
        )
        make_payment(self.order, "100.00")
        detail = self.client.get(url("stringing-order-detail", self.order)).data
        self.assertEqual(detail["balance"], "300.00")
        self.assertEqual(detail["payment_state"], "PARTIAL")

    def test_list_payments(self):
        make_payment(self.order, "100.00")
        make_payment(self.order, "50.00")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["results"][0]["amount"], "50.00")

    def test_404(self):
        response = self.client.get(url("stringing-order-payments", 999999))
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            url("stringing-order-payments", 999999),
            {"amount": "10", "payment_method": "CASH"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class SearchAPITests(StringingAPITestCase):
    def test_paged_list_and_filters(self):
        orders = [make_order(self.manager) for _ in range(21)]
        target = make_order(self.manager, customer=self.customer)
        change_status(order_id=target.pk, user=self.manager, to_status=S.IN_PROGRESS)

        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 22)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])
        self.assertEqual(response.data["results"][0]["id"], target.pk)
        self.assertNotIn("notes", response.data["results"][0])

        response = self.client.get(
            LIST_URL, {"status": "IN_PROGRESS", "search": "0917 123"}
        )
        self.assertEqual([o["id"] for o in response.data["results"]], [target.pk])
        self.assertEqual(len(orders), 21)

    def test_empty_result(self):
        response = self.client.get(LIST_URL, {"search": "nothing-matches"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_invalid_filter(self):
        response = self.client.get(LIST_URL, {"payment_state": "MAYBE"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("payment_state", response.data)

    def test_query_count_constant(self):
        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(LIST_URL).status_code, 200)
            return len(ctx.captured_queries)

        make_order(self.manager, customer=self.customer)
        count_queries()  # warm the user's permission cache
        few = count_queries()
        for _ in range(10):
            order = make_order(self.manager, customer=make_customer())
            make_payment(order, "10.00")
        self.assertEqual(count_queries(), few)


class CancelAPITests(StringingAPITestCase):
    def setUp(self):
        super().setUp()
        self.order = make_order(self.manager)
        self.url = url("stringing-order-cancel", self.order)

    def test_cancel(self):
        response = self.client.post(
            self.url, {"reason": "Changed mind", "materials_used": False}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], S.CANCELLED)
        self.assertEqual(response.data["cancellation_reason"], "Changed mind")
        self.assertEqual(response.data["cancelled_by"]["id"], self.manager.pk)
        self.assertIs(response.data["materials_used"], False)

    def test_materials_used_stored_and_audited(self):
        response = self.client.post(
            self.url, {"reason": "String cut", "materials_used": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertIs(self.order.materials_used, True)
        event = self.order.events.latest("id")
        self.assertEqual(event.event_type, "CANCELLED")
        self.assertEqual(event.changes, {"materials_used": True})

    def test_materials_used_required(self):
        response = self.client.post(self.url, {"reason": "Changed mind"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("materials_used", response.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.RECEIVED)

    def test_blank_reason(self):
        for data in ({}, {"reason": ""}, {"reason": "   "}):
            with self.subTest(data=data):
                response = self.client.post(self.url, data, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("reason", response.data)

    def test_already_cancelled(self):
        cancel_stringing_order(order_id=self.order.pk, user=self.manager, reason="x", materials_used=False)
        response = self.client.post(
            self.url, {"reason": "again", "materials_used": False}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_requires_permission(self):
        self.as_user(self.staff)
        response = self.client.post(
            self.url, {"reason": "x", "materials_used": False}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.RECEIVED)

    def test_404(self):
        response = self.client.post(
            url("stringing-order-cancel", 999999), {"reason": "x"}, format="json"
        )
        self.assertEqual(response.status_code, 404)


class HistoryAPITests(StringingAPITestCase):
    def test_history(self):
        order = make_order(self.manager)
        make_payment(order, "100.00")
        self.client.patch(
            url("stringing-order-detail", order),
            {"direct_cost": "200.00"},
            format="json",
        )
        response = self.client.get(url("stringing-order-history", order))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [e["type"] for e in response.data], ["CREATED", "PAYMENT", "UPDATED"]
        )
        self.assertEqual(response.data[0]["by"]["id"], self.manager.pk)

        self.as_user(self.staff)
        response = self.client.get(url("stringing-order-history", order))
        self.assertEqual([e["type"] for e in response.data], ["CREATED", "PAYMENT"])

    def test_404(self):
        response = self.client.get(url("stringing-order-history", 999999))
        self.assertEqual(response.status_code, 404)


class RevenueReportAPITests(StringingAPITestCase):
    URL = reverse("stringing-revenue-report")

    def test_report_shape(self):
        order = make_order(self.manager)
        make_payment(order, "400.00")
        order.refresh_from_db()
        day = order.paid_in_full_at.astimezone().date().isoformat()
        response = self.client.get(
            self.URL, {"date_from": "2000-01-01", "date_to": "2100-01-01"}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["orders_count"], 1)
        self.assertEqual(response.data["net_revenue"], "400.00")
        self.assertEqual(response.data["profit"], "220.00")
        self.assertEqual(response.data["date_from"], "2000-01-01")
        self.assertTrue(day)
        for key in (
            "gross_service_price",
            "total_discounts",
            "total_direct_cost",
            "total_refunds",
            "net_revenue_after_refunds",
            "profit_after_refunds",
            "cancelled_count",
            "unpaid_count",
            "outstanding_balance",
        ):
            self.assertIn(key, response.data)

    def test_invalid_dates(self):
        for params in (
            {},
            {"date_from": "2026-11-01"},
            {"date_from": "bad", "date_to": "2026-11-01"},
            {"date_from": "2026-11-05", "date_to": "2026-11-01"},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(self.URL, params).status_code, 400)

    def test_requires_permission(self):
        self.as_user(self.staff)
        response = self.client.get(
            self.URL, {"date_from": "2026-11-01", "date_to": "2026-11-30"}
        )
        self.assertEqual(response.status_code, 403)
