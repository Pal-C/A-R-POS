"""
Story-level run through the stringing API (quickstart.md): intake →
workshop → partial and full payment → pickup; a second order cancelled
and refunded; the revenue report checked.
"""

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from stringing.selectors import store_tz
from stringing.tests.factories import ALL_PERMISSIONS, make_customer, make_user


class StringingWorkflowTests(APITestCase):
    def setUp(self):
        self.cashier = make_user(username="cashier", perms=["sales.record_payment"])
        self.manager = make_user(username="manager", perms=ALL_PERMISSIONS)
        self.customer = make_customer(
            full_name="Ana Reyes", phone_number="0917 123 4567"
        )

    def call(self, method, url, data=None, expected=200):
        response = getattr(self.client, method)(url, data, format="json")
        self.assertEqual(
            response.status_code, expected, getattr(response, "data", None)
        )
        return response.data

    def order_url(self, name, order_id):
        return reverse(name, kwargs={"pk": order_id})

    def test_stringing_lifecycle(self):
        list_url = reverse("stringing-order-list-create")
        self.client.force_authenticate(self.cashier)

        # Intake (US1).
        order = self.call(
            "post",
            list_url,
            {
                "customer": self.customer.pk,
                "racket_description": "Yonex Astrox 88D, 4U",
                "string_type": "BG80",
                "tension": "26 lbs",
                "service_price": "450.00",
                "discount_amount": "50.00",
                "direct_cost": "180.00",
            },
            expected=201,
        )
        oid = order["id"]
        self.assertNotIn("direct_cost", order)

        # Workshop (US2) and payments (US3).
        status_url = self.order_url("stringing-order-status", oid)
        pay_url = self.order_url("stringing-order-payments", oid)
        self.call("post", status_url, {"status": "IN_PROGRESS"})
        self.call("post", pay_url, {"amount": "150.00", "payment_method": "CASH"}, 201)
        self.call("post", status_url, {"status": "READY"})
        self.call("post", status_url, {"status": "COMPLETED"}, expected=400)
        paid = self.call(
            "post", pay_url, {"amount": "250.00", "payment_method": "GCASH"}, 201
        )
        self.assertEqual(paid["order"]["payment_state"], "PAID")
        done = self.call("post", status_url, {"status": "COMPLETED"})
        self.assertEqual(done["status"], "COMPLETED")

        # Search (US4).
        found = self.call(
            "get", list_url, {"search": "09171234567", "status": "COMPLETED"}
        )
        self.assertEqual([o["id"] for o in found["results"]], [oid])

        # Second order: paid, then cancelled and refunded (US5).
        other = self.call(
            "post",
            list_url,
            {
                "racket_description": "Arcsaber 11",
                "string_type": "BG66",
                "service_price": "300.00",
            },
            expected=201,
        )
        other_pay = self.order_url("stringing-order-payments", other["id"])
        self.call(
            "post", other_pay, {"amount": "300.00", "payment_method": "CASH"}, 201
        )
        cancel_url = self.order_url("stringing-order-cancel", other["id"])
        self.call("post", cancel_url, {"reason": "Customer changed mind"}, expected=403)

        self.client.force_authenticate(self.manager)
        cancelled = self.call("post", cancel_url, {"reason": "Customer changed mind"})
        self.assertEqual(cancelled["refund_due"], "300.00")
        refunded = self.call(
            "post",
            other_pay,
            {
                "amount": "300.00",
                "payment_method": "CASH",
                "payment_type": "REFUND",
                "reason": "Cancelled",
            },
            201,
        )
        self.assertEqual(refunded["order"]["refund_due"], "0.00")

        history = self.call(
            "get", self.order_url("stringing-order-history", other["id"])
        )
        self.assertEqual(
            [e["type"] for e in history], ["CREATED", "PAYMENT", "CANCELLED", "PAYMENT"]
        )

        # Revenue (US6): only the completed, fully paid order counts.
        today = timezone.now().astimezone(store_tz()).date().isoformat()
        report = self.call(
            "get",
            reverse("stringing-revenue-report"),
            {"date_from": today, "date_to": today},
        )
        self.assertEqual(report["orders_count"], 1)
        self.assertEqual(report["net_revenue"], "400.00")
        self.assertEqual(report["total_direct_cost"], "180.00")
        self.assertEqual(report["profit"], "220.00")
        self.assertEqual(report["cancelled_count"], 1)
