"""SaleEvent and sale_date model rules (data-model.md)."""

from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from sales.models import Sale, SaleEvent
from sales.services import create_draft_sale
from sales.tests.factories import line, make_product, make_user


class SaleEventConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.sale = create_draft_sale(user=self.user, items=[line(make_product(), 1)])

    def make_event(self, reason):
        return SaleEvent.objects.create(
            sale=self.sale,
            action=SaleEvent.Action.CUSTOMER_CHANGED,
            reason=reason,
            performed_by=self.user,
        )

    def test_reason_is_required(self):
        for reason in ("", "   "):
            with self.subTest(reason=repr(reason)):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.make_event(reason)

    def test_sale_and_user_with_history_are_protected(self):
        self.make_event("Customer asked for a receipt")

        with self.assertRaises(ProtectedError):
            self.sale.delete()
        with self.assertRaises(ProtectedError):
            self.user.delete()


class SaleDateConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.sale = create_draft_sale(user=self.user, items=[line(make_product(), 1)])

    def test_drafts_may_have_no_sale_date(self):
        self.assertIsNone(self.sale.sale_date)

    def test_finalized_sales_require_a_sale_date(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Sale.objects.filter(pk=self.sale.pk).update(
                status=Sale.Status.COMPLETED, sale_date=None
            )

    def test_finalized_sale_with_date_is_valid(self):
        Sale.objects.filter(pk=self.sale.pk).update(
            status=Sale.Status.COMPLETED, sale_date=date(2026, 11, 27)
        )
