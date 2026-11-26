"""Every pre-order endpoint requires authentication (FR-026)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from preorders.tests.factories import make_preorder, make_user


class UnauthenticatedAccessTests(APITestCase):
    def test_every_endpoint_requires_authentication(self):
        preorder = make_preorder(make_user())
        pk = {"pk": preorder.pk}
        product = {"product_id": preorder.product_id}
        calls = [
            ("get", reverse("preorder-list-create"), None),
            ("post", reverse("preorder-list-create"), {}),
            ("get", reverse("preorder-detail", kwargs=pk), None),
            ("patch", reverse("preorder-detail", kwargs=pk), {}),
            ("post", reverse("preorder-status", kwargs=pk), {}),
            ("post", reverse("preorder-fulfill", kwargs=pk), {}),
            ("post", reverse("preorder-cancel", kwargs=pk), {}),
            ("get", reverse("preorder-payments", kwargs=pk), None),
            ("post", reverse("preorder-payments", kwargs=pk), {}),
            ("get", reverse("preorder-history", kwargs=pk), None),
            ("get", reverse("preorder-product-summary", kwargs=product), None),
            ("post", reverse("preorder-product-arrivals", kwargs=product), {}),
        ]
        for method, url, data in calls:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, data, format="json")
                self.assertIn(response.status_code, (401, 403))
