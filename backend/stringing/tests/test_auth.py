"""Every stringing endpoint requires authentication (FR-030)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from stringing.tests.factories import make_order, make_user


class UnauthenticatedAccessTests(APITestCase):
    def test_every_endpoint_requires_authentication(self):
        order = make_order(make_user())
        pk = {"pk": order.pk}
        calls = [
            ("get", reverse("stringing-order-list-create"), None),
            ("post", reverse("stringing-order-list-create"), {}),
            ("get", reverse("stringing-order-detail", kwargs=pk), None),
            ("patch", reverse("stringing-order-detail", kwargs=pk), {}),
            ("post", reverse("stringing-order-status", kwargs=pk), {}),
            ("post", reverse("stringing-order-cancel", kwargs=pk), {}),
            ("get", reverse("stringing-order-payments", kwargs=pk), None),
            ("post", reverse("stringing-order-payments", kwargs=pk), {}),
            ("get", reverse("stringing-order-history", kwargs=pk), None),
            ("get", reverse("stringing-revenue-report"), None),
        ]
        for method, url, data in calls:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, data, format="json")
                self.assertIn(response.status_code, (401, 403))
