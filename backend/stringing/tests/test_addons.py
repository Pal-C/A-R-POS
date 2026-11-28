"""Add-on, colour and store-string fields on StringingOrder (specs/007 R1, R4)."""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from stringing.models import StringingOrder
from stringing.selectors import order_queryset
from stringing.services import update_stringing_order
from stringing.tests.factories import make_order, make_payment, make_user


class AddOnConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)

    def assert_rejected(self, **values):
        with self.assertRaises(IntegrityError), transaction.atomic():
            StringingOrder.objects.filter(pk=self.order.pk).update(**values)

    def test_negative_stencil_price_rejected(self):
        self.assert_rejected(has_stencil=True, stencil_price=Decimal("-1.00"))

    def test_negative_grip_price_rejected(self):
        self.assert_rejected(has_grip=True, grip_price=Decimal("-1.00"))

    def test_stencil_price_without_stencil_rejected(self):
        self.assert_rejected(has_stencil=False, stencil_price=Decimal("50.00"))

    def test_grip_price_without_grip_rejected(self):
        self.assert_rejected(has_grip=False, grip_price=Decimal("120.00"))

    def test_discount_may_cover_add_ons(self):
        StringingOrder.objects.filter(pk=self.order.pk).update(
            has_grip=True,
            grip_price=Decimal("120.00"),
            discount_amount=Decimal("570.00"),
        )

    def test_discount_above_service_and_add_ons_rejected(self):
        self.assert_rejected(
            has_grip=True,
            grip_price=Decimal("120.00"),
            discount_amount=Decimal("570.01"),
        )

    def test_materials_used_on_open_order_rejected(self):
        self.assert_rejected(materials_used=False)

    def test_client_transaction_id_unique(self):
        key = uuid.uuid4()
        StringingOrder.objects.filter(pk=self.order.pk).update(
            client_transaction_id=key
        )
        other = make_order(self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StringingOrder.objects.filter(pk=other.pk).update(client_transaction_id=key)


class AddOnTotalTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_defaults_mean_no_add_ons(self):
        order = make_order(self.user)
        self.assertEqual(order.string_color, "")
        self.assertFalse(order.has_stencil or order.has_grip or order.string_from_store)
        self.assertEqual(order.add_ons_total, Decimal("0.00"))
        self.assertEqual(order.total_amount, Decimal("400.00"))
        self.assertIsNone(order.materials_used)

    def test_total_includes_add_ons(self):
        order = make_order(
            self.user,
            service_price=Decimal("350.00"),
            has_stencil=True,
            stencil_price=Decimal("50.00"),
            has_grip=True,
            grip_price=Decimal("120.00"),
            string_from_store=True,
            discount_amount=Decimal("100.00"),
            string_color="White",
        )
        self.assertEqual(order.add_ons_total, Decimal("170.00"))
        self.assertEqual(order.total_amount, Decimal("420.00"))
        annotated = order_queryset().get(pk=order.pk)
        self.assertEqual(annotated.order_total, Decimal("420.00"))
        self.assertEqual(order.string_color, "White")

    def test_add_on_price_without_add_on_refused(self):
        with self.assertRaises(ValidationError) as ctx:
            make_order(self.user, has_stencil=False, stencil_price=Decimal("50.00"))
        self.assertIn("stencil_price", ctx.exception.message_dict)

    def test_discount_above_service_and_add_ons_refused(self):
        with self.assertRaises(ValidationError) as ctx:
            make_order(
                self.user,
                service_price=Decimal("100.00"),
                has_grip=True,
                grip_price=Decimal("20.00"),
                discount_amount=Decimal("120.01"),
            )
        self.assertIn("discount_amount", ctx.exception.message_dict)

    def test_update_add_ons_records_changes(self):
        order = make_order(self.user)
        update_stringing_order(
            order_id=order.pk,
            user=self.user,
            has_stencil=True,
            stencil_price=Decimal("50.00"),
            string_color="Red",
        )
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal("450.00"))
        event = order.events.latest("id")
        self.assertEqual(event.changes["has_stencil"], [False, True])
        self.assertEqual(event.changes["stencil_price"], ["0.00", "50.00"])
        self.assertEqual(event.changes["string_color"], ["", "Red"])

    def test_removing_add_on_below_paid_refused(self):
        order = make_order(
            self.user,
            discount_amount=Decimal("0.00"),
            has_grip=True,
            grip_price=Decimal("100.00"),
        )
        make_payment(order, "550.00")
        with self.assertRaises(ValidationError):
            update_stringing_order(
                order_id=order.pk,
                user=self.user,
                has_grip=False,
                grip_price=Decimal("0.00"),
            )
