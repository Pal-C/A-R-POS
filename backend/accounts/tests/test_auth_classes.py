"""The API distinguishes "not signed in" (401) from "not permitted" (403) (research R2)."""

import base64

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from customers.tests.factories import make_customer, make_user


class AuthenticationStatusTests(APITestCase):
    def test_anonymous_request_returns_401_with_session_challenge(self):
        response = self.client.get(reverse("customer-list-create"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], "Session")

    def test_authenticated_user_without_permission_gets_403(self):
        user = make_user()
        customer = make_customer(full_name="Ana", phone_number="0917")
        self.client.force_authenticate(user)

        response = self.client.delete(
            reverse("customer-detail", kwargs={"pk": customer.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_http_basic_credentials_are_not_accepted(self):
        get_user_model().objects.create_user(username="basic", password="pw-12345!")
        token = base64.b64encode(b"basic:pw-12345!").decode()

        response = self.client.get(
            reverse("customer-list-create"), HTTP_AUTHORIZATION=f"Basic {token}"
        )

        self.assertEqual(response.status_code, 401)
