"""ProductEvent model rules (data-model.md ProductEvent)."""

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from catalog.models import ProductEvent
from sales.tests.factories import make_product, make_user


class ProductEventConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()

    def make_event(self, action, reason):
        return ProductEvent.objects.create(
            product=self.product, action=action, reason=reason, performed_by=self.user
        )

    def test_created_event_needs_no_reason(self):
        event = self.make_event(ProductEvent.Action.CREATED, "")

        self.assertEqual(event.changes, {})

    def test_other_actions_require_a_reason(self):
        for action in (
            ProductEvent.Action.UPDATED,
            ProductEvent.Action.DEACTIVATED,
            ProductEvent.Action.REACTIVATED,
        ):
            for reason in ("", "   "):
                with self.subTest(action=action, reason=repr(reason)):
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        self.make_event(action, reason)

    def test_products_with_history_cannot_be_deleted(self):
        self.make_event(ProductEvent.Action.CREATED, "")

        with self.assertRaises(ProtectedError):
            self.product.delete()

    def test_users_with_history_cannot_be_deleted(self):
        self.make_event(ProductEvent.Action.CREATED, "")

        with self.assertRaises(ProtectedError):
            self.user.delete()
