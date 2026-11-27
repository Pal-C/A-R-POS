"""Login throttling and CSRF behind a reverse proxy (code-review findings 1 and 2)."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

PASSWORD = "correct-horse-42"


class LoginThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        get_user_model().objects.create_user(username="maria", password=PASSWORD)
        self.url = reverse("auth-login")

    def attempt(self, username="maria", password="wrong", **headers):
        return self.client.post(
            self.url,
            {"username": username, "password": password},
            format="json",
            **headers,
        )

    def test_spoofed_forwarded_for_headers_do_not_reset_the_limit(self):
        for n in range(10):
            self.attempt(username=f"user{n}", HTTP_X_FORWARDED_FOR=f"10.0.0.{n}")

        response = self.attempt(username="other", HTTP_X_FORWARDED_FOR="10.9.9.9")

        self.assertEqual(response.status_code, 429)

    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "accounts.authentication.SessionAuthentication"
            ],
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.IsAuthenticated"
            ],
            "NUM_PROXIES": 1,
        }
    )
    def test_behind_one_proxy_clients_are_limited_separately(self):
        for _ in range(10):
            self.attempt(
                username="someone",
                HTTP_X_FORWARDED_FOR="203.0.113.5",
                REMOTE_ADDR="10.0.0.1",
            )

        other_client = self.attempt(
            username="maria",
            password=PASSWORD,
            HTTP_X_FORWARDED_FOR="203.0.113.6",
            REMOTE_ADDR="10.0.0.1",
        )

        self.assertEqual(other_client.status_code, 200)

    def test_one_username_is_limited_across_client_addresses(self):
        for n in range(10):
            self.attempt(REMOTE_ADDR=f"192.0.2.{n}")

        response = self.attempt(password=PASSWORD, REMOTE_ADDR="192.0.2.200")

        self.assertEqual(response.status_code, 429)

    def test_username_limit_ignores_case_and_whitespace(self):
        for n in range(10):
            self.attempt(
                username=" MARIA " if n % 2 else "maria", REMOTE_ADDR=f"192.0.2.{n}"
            )

        response = self.attempt(password=PASSWORD, REMOTE_ADDR="192.0.2.200")

        self.assertEqual(response.status_code, 429)


@override_settings(ALLOWED_HOSTS=["pos.example"])
class LoginBehindHttpsProxyTests(APITestCase):
    def setUp(self):
        cache.clear()
        get_user_model().objects.create_user(username="maria", password=PASSWORD)
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.get(reverse("auth-csrf"), HTTP_HOST="pos.example")
        self.token = self.client.cookies["csrftoken"].value

    def login(self, **headers):
        return self.client.post(
            reverse("auth-login"),
            {"username": "maria", "password": PASSWORD},
            format="json",
            HTTP_HOST="pos.example",
            HTTP_ORIGIN="https://pos.example",
            HTTP_X_CSRFTOKEN=self.token,
            **headers,
        )

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_login_succeeds_when_proxy_reports_https(self):
        response = self.login(HTTP_X_FORWARDED_PROTO="https")

        self.assertEqual(response.status_code, 200)

    @override_settings(CSRF_TRUSTED_ORIGINS=["https://pos.example"])
    def test_login_succeeds_with_trusted_origin(self):
        response = self.login()

        self.assertEqual(response.status_code, 200)

    def test_login_is_rejected_without_proxy_configuration(self):
        response = self.login()

        self.assertEqual(response.status_code, 403)
