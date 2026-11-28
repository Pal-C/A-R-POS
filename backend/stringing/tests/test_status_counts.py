"""Status chip counts (specs/007 R5)."""

from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from stringing.models import StringingOrder
from stringing.services import cancel_stringing_order, change_status
from stringing.tests.factories import make_customer, make_order, make_payment, make_user

COUNTS_URL = reverse("stringing-order-status-counts")
S = StringingOrder.Status


class StatusCountsAPITests(APITestCase):
    def setUp(self):
        self.user = make_user(perms=["stringing.cancel_stringingorder"])
        self.client.force_authenticate(self.user)
        mika = make_customer(full_name="Mika Reyes")
        self.received = make_order(self.user, customer=mika)
        self.in_progress = make_order(self.user)
        change_status(
            order_id=self.in_progress.pk, user=self.user, to_status=S.IN_PROGRESS
        )
        self.ready = make_order(self.user, customer=mika)
        for step in (S.IN_PROGRESS, S.READY):
            change_status(order_id=self.ready.pk, user=self.user, to_status=step)
        self.cancelled = make_order(self.user)
        cancel_stringing_order(
            order_id=self.cancelled.pk, user=self.user, reason="x", materials_used=False
        )
        make_payment(self.ready, "400.00")

    def get(self, **params):
        response = self.client.get(COUNTS_URL, params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_counts_all_statuses(self):
        self.assertEqual(
            self.get(),
            {
                "all": 4,
                "RECEIVED": 1,
                "IN_PROGRESS": 1,
                "READY": 1,
                "COMPLETED": 0,
                "CANCELLED": 1,
            },
        )

    def test_status_param_ignored(self):
        self.assertEqual(self.get(status="READY")["all"], 4)

    def test_search(self):
        data = self.get(search="Mika")
        self.assertEqual(data["all"], 2)
        self.assertEqual(data["RECEIVED"], 1)
        self.assertEqual(data["READY"], 1)

    def test_payment_state(self):
        data = self.get(payment_state="PAID")
        self.assertEqual(data["all"], 1)
        self.assertEqual(data["READY"], 1)

    def test_date_range(self):
        StringingOrder.objects.filter(pk=self.received.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        today = timezone.localdate()
        data = self.get(received_from=today.isoformat(), received_to=today.isoformat())
        self.assertEqual(data["all"], 3)
        self.assertEqual(data["RECEIVED"], 0)

    def test_invalid_date(self):
        response = self.client.get(COUNTS_URL, {"received_from": "yesterday"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("received_from", response.data)

    def test_unauthenticated(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(COUNTS_URL).status_code, (401, 403))

    def test_one_query(self):
        with CaptureQueriesContext(connection) as ctx:
            self.get(search="Mika", payment_state="PAID")
        self.assertEqual(len(ctx.captured_queries), 1)
