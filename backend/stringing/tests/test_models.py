"""Database constraints and permissions on StringingOrder (constitution II)."""

from decimal import Decimal

from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from stringing.models import StringingOrder
from stringing.tests.factories import make_order, make_user


class StringingOrderConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)

    def assert_rejected(self, **values):
        with self.assertRaises(IntegrityError), transaction.atomic():
            StringingOrder.objects.filter(pk=self.order.pk).update(**values)

    def test_negative_price_rejected(self):
        self.assert_rejected(service_price=Decimal("-1.00"), discount_amount=0)

    def test_negative_discount_rejected(self):
        self.assert_rejected(discount_amount=Decimal("-1.00"))

    def test_negative_cost_rejected(self):
        self.assert_rejected(direct_cost=Decimal("-0.01"))

    def test_discount_above_price_rejected(self):
        self.assert_rejected(discount_amount=Decimal("450.01"))

    def test_blank_racket_rejected(self):
        self.assert_rejected(racket_description="   ")

    def test_blank_string_type_rejected(self):
        self.assert_rejected(string_type="")

    def test_cancelled_without_audit_fields_rejected(self):
        self.assert_rejected(status=StringingOrder.Status.CANCELLED)

    def test_cancelled_without_reason_rejected(self):
        self.assert_rejected(
            status=StringingOrder.Status.CANCELLED,
            cancelled_at=timezone.now(),
            cancelled_by=self.user,
            cancellation_reason="",
        )

    def test_cancel_fields_on_open_order_rejected(self):
        self.assert_rejected(cancelled_at=timezone.now())

    def test_completed_without_time_rejected(self):
        self.assert_rejected(status=StringingOrder.Status.COMPLETED)

    def test_valid_cancelled_row_accepted(self):
        StringingOrder.objects.filter(pk=self.order.pk).update(
            status=StringingOrder.Status.CANCELLED,
            cancelled_at=timezone.now(),
            cancelled_by=self.user,
            cancellation_reason="Changed mind",
        )

    def test_order_number_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            StringingOrder.objects.create(
                order_number=self.order.order_number,
                racket_description="R",
                string_type="S",
                service_price=Decimal("1.00"),
                created_by=self.user,
            )


class StringingPermissionTests(TestCase):
    def test_permissions_exist(self):
        codenames = set(
            Permission.objects.filter(content_type__app_label="stringing").values_list(
                "codename", flat=True
            )
        )
        self.assertIn("cancel_stringingorder", codenames)
        self.assertIn("view_stringing_financials", codenames)
