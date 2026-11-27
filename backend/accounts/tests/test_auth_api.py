"""Auth endpoints used by the frontend (specs/004-frontend-foundation/contracts/auth-api.md)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

User = get_user_model()

PASSWORD = "correct-horse-42"
CURRENT_USER_KEYS = {
    "id",
    "username",
    "first_name",
    "last_name",
    "display_name",
    "is_superuser",
    "permissions",
}


def make_staff(username="maria", **kwargs):
    return User.objects.create_user(username=username, password=PASSWORD, **kwargs)


class CsrfEndpointTests(APITestCase):
    def test_sets_csrf_cookie(self):
        response = self.client.get(reverse("auth-csrf"))

        self.assertEqual(response.status_code, 204)
        self.assertIn("csrftoken", response.cookies)


class LoginTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("auth-login")
        self.user = make_staff(first_name="Maria", last_name="Santos")

    def test_success_returns_current_user_and_starts_session(self):
        response = self.client.post(
            self.url, {"username": "maria", "password": PASSWORD}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), CURRENT_USER_KEYS)
        self.assertEqual(response.data["username"], "maria")
        self.assertEqual(response.data["display_name"], "Maria Santos")
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 200)

    def test_bad_credentials_and_inactive_users_get_the_same_generic_error(self):
        User.objects.create_user(username="gone", password=PASSWORD, is_active=False)
        attempts = [
            {"username": "maria", "password": "wrong"},
            {"username": "nobody", "password": PASSWORD},
            {"username": "gone", "password": PASSWORD},
        ]
        for body in attempts:
            with self.subTest(username=body["username"]):
                response = self.client.post(self.url, body, format="json")

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.data,
                    {"non_field_errors": ["Invalid username or password."]},
                )
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)

    def test_missing_fields_return_field_errors(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)
        self.assertIn("password", response.data)

    def test_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)

        response = client.post(
            self.url, {"username": "maria", "password": PASSWORD}, format="json"
        )

        self.assertEqual(response.status_code, 403)

    def test_succeeds_with_csrf_token_from_csrf_endpoint(self):
        client = APIClient(enforce_csrf_checks=True)
        client.get(reverse("auth-csrf"))
        token = client.cookies["csrftoken"].value

        response = client.post(
            self.url,
            {"username": "maria", "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)

    def test_login_replaces_an_existing_session(self):
        make_staff(username="jo")
        self.client.post(
            self.url, {"username": "maria", "password": PASSWORD}, format="json"
        )

        self.client.post(
            self.url, {"username": "jo", "password": PASSWORD}, format="json"
        )

        self.assertEqual(self.client.get(reverse("auth-me")).data["username"], "jo")

    def test_repeated_attempts_are_throttled(self):
        for _ in range(10):
            self.client.post(
                self.url, {"username": "maria", "password": "wrong"}, format="json"
            )

        response = self.client.post(
            self.url, {"username": "maria", "password": PASSWORD}, format="json"
        )

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)


class LogoutTests(APITestCase):
    def setUp(self):
        make_staff()

    def test_logout_ends_the_session(self):
        self.client.login(username="maria", password=PASSWORD)

        response = self.client.post(reverse("auth-logout"))

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)

    def test_logout_while_signed_out_is_a_no_op(self):
        response = self.client.post(reverse("auth-logout"))

        self.assertEqual(response.status_code, 204)

    def test_logout_requires_csrf_token_when_signed_in(self):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username="maria", password=PASSWORD)

        response = client.post(reverse("auth-logout"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(client.get(reverse("auth-me")).status_code, 200)


class MeTests(APITestCase):
    def test_anonymous_gets_401(self):
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, 401)

    def test_returns_identity_and_permissions_from_user_and_groups(self):
        user = make_staff()
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="customers", codename="archive_customer"
            )
        )
        group = Group.objects.create(name="Cashier")
        group.permissions.add(
            Permission.objects.get(
                content_type__app_label="customers", codename="delete_customer"
            )
        )
        user.groups.add(group)
        self.client.force_authenticate(user)

        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), CURRENT_USER_KEYS)
        self.assertEqual(
            response.data["permissions"],
            ["customers.archive_customer", "customers.delete_customer"],
        )
        self.assertFalse(response.data["is_superuser"])

    def test_display_name_falls_back_to_username(self):
        self.client.force_authenticate(make_staff(username="solo"))

        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.data["display_name"], "solo")
