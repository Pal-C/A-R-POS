"""Every customer endpoint rejects unauthenticated requests (constitution II)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from customers.models import Customer, CustomerAuditEvent
from customers.tests.factories import make_customer


class UnauthenticatedSweepTests(APITestCase):
    def test_every_endpoint_rejects_anonymous_requests(self):
        customer = make_customer(full_name="Ana", phone_number="0917")
        pk = {"pk": customer.pk}
        requests = [
            ("get", reverse("customer-list-create"), None),
            ("post", reverse("customer-list-create"), {"full_name": "Intruder"}),
            ("get", reverse("customer-detail", kwargs=pk), None),
            ("patch", reverse("customer-detail", kwargs=pk), {"full_name": "Hacked"}),
            ("delete", reverse("customer-detail", kwargs=pk), None),
            ("post", reverse("customer-archive", kwargs=pk), None),
            ("post", reverse("customer-reactivate", kwargs=pk), None),
            ("get", reverse("customer-sales", kwargs=pk), None),
            ("get", reverse("customer-stringing-orders", kwargs=pk), None),
            ("get", reverse("customer-preorders", kwargs=pk), None),
            ("get", reverse("customer-phone-matches"), {"phone": "0917"}),
        ]

        for method, url, data in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, data, format="json")
                self.assertIn(response.status_code, (401, 403))

        customer.refresh_from_db()
        self.assertEqual(customer.full_name, "Ana")
        self.assertTrue(customer.is_active)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertFalse(CustomerAuditEvent.objects.exists())
