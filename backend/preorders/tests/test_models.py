"""Database constraints and permissions on PreOrder (constitution II)."""

from decimal import Decimal

from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from preorders.models import PreOrder
from preorders.tests.factories import make_preorder, make_user


class PreOrderConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.preorder = make_preorder(self.user)

    def assert_rejected(self, **values):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PreOrder.objects.filter(pk=self.preorder.pk).update(**values)

    def test_zero_quantity_rejected(self):
        self.assert_rejected(quantity=0)

    def test_negative_price_rejected(self):
        self.assert_rejected(agreed_unit_price=Decimal("-0.01"))

    def test_cancelled_without_audit_fields_rejected(self):
        self.assert_rejected(status=PreOrder.Status.CANCELLED)

    def test_cancelled_without_reason_rejected(self):
        self.assert_rejected(
            status=PreOrder.Status.CANCELLED,
            cancelled_at=timezone.now(),
            cancelled_by=self.user,
        )

    def test_cancel_fields_on_open_order_rejected(self):
        self.assert_rejected(cancelled_by=self.user)

    def test_fulfilled_without_audit_fields_rejected(self):
        self.assert_rejected(status=PreOrder.Status.FULFILLED)
        self.assert_rejected(
            status=PreOrder.Status.FULFILLED, fulfilled_at=timezone.now()
        )

    def test_fulfilled_fields_on_open_order_rejected(self):
        self.assert_rejected(fulfilled_at=timezone.now())

    def test_settled_only_when_fulfilled(self):
        self.assert_rejected(settled_at=timezone.now())

    def test_valid_fulfilled_row_accepted(self):
        PreOrder.objects.filter(pk=self.preorder.pk).update(
            status=PreOrder.Status.FULFILLED,
            fulfilled_at=timezone.now(),
            fulfilled_by=self.user,
        )

    def test_order_number_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PreOrder.objects.create(
                order_number=self.preorder.order_number,
                customer=self.preorder.customer,
                product=self.preorder.product,
                quantity=1,
                agreed_unit_price=Decimal("1.00"),
                created_by=self.user,
            )


class PreOrderPermissionTests(TestCase):
    def test_permissions_exist(self):
        codenames = set(
            Permission.objects.filter(content_type__app_label="preorders").values_list(
                "codename", flat=True
            )
        )
        self.assertIn("cancel_preorder", codenames)
        self.assertIn("override_preorder_price", codenames)
