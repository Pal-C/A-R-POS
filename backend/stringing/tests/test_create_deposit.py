"""Create with add-ons and a deposit, idempotent by client_transaction_id (specs/007 R3)."""

import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from sales.models import Payment
from stringing.models import StringingOrder
from stringing.services import take_in_order
from stringing.tests.factories import ALL_PERMISSIONS, make_customer, make_user

LIST_URL = reverse("stringing-order-list-create")

FIELDS = {
    "racket_description": "Arcsaber 11",
    "string_type": "BG80",
    "string_color": "White",
    "tension": "27 lbs",
    "service_price": Decimal("350.00"),
    "has_stencil": True,
    "stencil_price": Decimal("50.00"),
    "has_grip": True,
    "grip_price": Decimal("120.00"),
    "string_from_store": True,
    "discount_amount": Decimal("100.00"),
}


def deposit(amount, method=Payment.Method.GCASH):
    return {"amount": Decimal(amount), "payment_method": method}


class TakeInServiceTests(TestCase):
    def setUp(self):
        self.user = make_user(perms=["sales.record_payment"])

    def test_with_deposit(self):
        order, created = take_in_order(
            user=self.user, deposit=deposit("270.00"), **FIELDS
        )
        self.assertTrue(created)
        order = StringingOrder.objects.get(pk=order.pk)
        self.assertEqual(order.status, StringingOrder.Status.RECEIVED)
        self.assertEqual(order.total_amount, Decimal("420.00"))
        payments = Payment.objects.filter(stringing_order=order)
        self.assertEqual(payments.count(), 1)
        payment = payments.get()
        self.assertEqual(payment.amount, Decimal("270.00"))
        self.assertEqual(payment.payment_type, Payment.PaymentType.RECEIPT)
        self.assertEqual(payment.payment_method, Payment.Method.GCASH)
        self.assertIsNone(order.paid_in_full_at)

    def test_full_deposit_pays_in_full(self):
        order, _ = take_in_order(user=self.user, deposit=deposit("420.00"), **FIELDS)
        order.refresh_from_db()
        self.assertIsNotNone(order.paid_in_full_at)

    def test_without_deposit(self):
        order, created = take_in_order(user=self.user, **FIELDS)
        self.assertTrue(created)
        self.assertFalse(Payment.objects.filter(stringing_order=order).exists())

    def test_zero_total_paid_in_full(self):
        fields = {
            **FIELDS,
            "has_stencil": False,
            "stencil_price": Decimal("0"),
            "has_grip": False,
            "grip_price": Decimal("0"),
            "discount_amount": Decimal("350.00"),
        }
        order, _ = take_in_order(user=self.user, **fields)
        self.assertEqual(order.total_amount, Decimal("0.00"))
        self.assertIsNotNone(order.paid_in_full_at)

    def test_rejections_save_nothing(self):
        cases = [
            ({"deposit": deposit("0.00")}, "deposit"),
            ({"deposit": deposit("420.01")}, "deposit"),
            ({"deposit": deposit("10.00", method="BITCOIN")}, "deposit"),
            ({"racket_description": "  "}, "racket_description"),
            ({"discount_amount": Decimal("520.01")}, "discount_amount"),
            ({"has_grip": False}, "grip_price"),
        ]
        for overrides, field in cases:
            with self.subTest(field=field, overrides=overrides):
                with self.assertRaises(ValidationError) as ctx:
                    take_in_order(user=self.user, **{**FIELDS, **overrides})
                self.assertIn(field, ctx.exception.message_dict)
                self.assertFalse(StringingOrder.objects.exists())
                self.assertFalse(Payment.objects.exists())

    def test_deposit_needs_permission(self):
        with self.assertRaises(PermissionDenied):
            take_in_order(user=make_user(), deposit=deposit("10.00"), **FIELDS)
        self.assertFalse(StringingOrder.objects.exists())

    def test_idempotent_repeat(self):
        key = uuid.uuid4()
        first, created = take_in_order(
            user=self.user,
            deposit=deposit("270.00"),
            client_transaction_id=key,
            **FIELDS,
        )
        again, created_again = take_in_order(
            user=self.user,
            deposit=deposit("270.00"),
            client_transaction_id=key,
            **FIELDS,
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(StringingOrder.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

    def test_key_reused_by_other_user_refused(self):
        key = uuid.uuid4()
        take_in_order(user=self.user, client_transaction_id=key, **FIELDS)
        with self.assertRaises(ValidationError) as ctx:
            take_in_order(user=make_user(), client_transaction_id=key, **FIELDS)
        self.assertIn("client_transaction_id", ctx.exception.message_dict)
        self.assertEqual(StringingOrder.objects.count(), 1)


class TakeInAPITests(APITestCase):
    payload = {
        "racket_description": "Arcsaber 11",
        "string_type": "BG80",
        "string_color": "White",
        "tension": "27 lbs",
        "service_price": "350.00",
        "has_stencil": True,
        "stencil_price": "50.00",
        "has_grip": False,
        "grip_price": "0.00",
        "string_from_store": True,
        "discount_amount": "100.00",
    }

    def setUp(self):
        self.manager = make_user(perms=ALL_PERMISSIONS)
        self.customer = make_customer()
        self.client.force_authenticate(self.manager)

    def post(self, **extra):
        return self.client.post(LIST_URL, {**self.payload, **extra}, format="json")

    def test_create_with_deposit_shape(self):
        response = self.post(
            customer=self.customer.pk,
            deposit={"amount": "270.00", "payment_method": "GCASH"},
            client_transaction_id=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        self.assertEqual(data["string_color"], "White")
        self.assertIs(data["string_from_store"], True)
        self.assertIs(data["has_stencil"], True)
        self.assertEqual(data["stencil_price"], "50.00")
        self.assertIs(data["has_grip"], False)
        self.assertEqual(data["add_ons_total"], "50.00")
        self.assertEqual(data["total_amount"], "300.00")
        self.assertEqual(data["amount_paid"], "270.00")
        self.assertEqual(data["balance"], "30.00")
        self.assertEqual(data["payment_state"], "PARTIAL")
        self.assertIsNone(data["materials_used"])

    def test_repeat_returns_200(self):
        key = str(uuid.uuid4())
        first = self.post(client_transaction_id=key)
        second = self.post(client_transaction_id=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])

    def test_deposit_without_permission_forbidden(self):
        self.client.force_authenticate(make_user())
        response = self.post(deposit={"amount": "10.00", "payment_method": "CASH"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(StringingOrder.objects.exists())

    def test_create_without_deposit_needs_no_permission(self):
        self.client.force_authenticate(make_user())
        self.assertEqual(self.post().status_code, 201)

    def test_validation_errors(self):
        cases = [
            ({"deposit": {"amount": "500.00", "payment_method": "CASH"}}, "deposit"),
            ({"deposit": {"amount": "10.00"}}, "deposit"),
            ({"stencil_price": "-1.00"}, "stencil_price"),
            ({"has_stencil": False}, "stencil_price"),
            ({"discount_amount": "400.01"}, "discount_amount"),
            ({"client_transaction_id": "nope"}, "client_transaction_id"),
        ]
        for extra, field in cases:
            with self.subTest(field=field, extra=extra):
                response = self.post(**extra)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        self.assertFalse(StringingOrder.objects.exists())

    def test_unauthenticated(self):
        self.client.force_authenticate(None)
        self.assertIn(self.post().status_code, (401, 403))

    def test_create_query_count(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.post(
                customer=self.customer.pk,
                deposit={"amount": "100.00", "payment_method": "CASH"},
                client_transaction_id=str(uuid.uuid4()),
            )
        self.assertEqual(response.status_code, 201)
        # A fixed count: idempotency lookup, savepoints, sequence, order,
        # event, customer check, the payment (with its locks and sync) and
        # the detail read.
        self.assertLessEqual(len(ctx.captured_queries), 20)
