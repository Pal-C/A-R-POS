"""Data migration 0007 backfills sale_date from finalized_at (store-local date)."""

from datetime import UTC, datetime
from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TestCase

from sales.models import Sale
from sales.services import create_draft_sale
from sales.tests.factories import line, make_product, make_user

migration = import_module("sales.migrations.0007_backfill_sale_date")


class BackfillSaleDateTests(TestCase):
    def test_uses_the_store_local_date_and_skips_drafts(self):
        user = make_user()
        late_utc = datetime(2026, 11, 8, 20, 30, tzinfo=UTC)  # 11/09 in Manila
        finalized = create_draft_sale(user=user, items=[line(make_product(), 1)])
        draft = create_draft_sale(user=user, items=[line(make_product(), 1)])
        constraint = next(
            c
            for c in Sale._meta.constraints
            if c.name == "sale_date_required_when_finalized"
        )
        # Recreate the pre-backfill state: the constraint (0008) doesn't exist yet.
        # Deferred FK checks must run before the table can be altered.
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        with connection.schema_editor() as editor:
            editor.remove_constraint(Sale, constraint)
        Sale.objects.filter(pk=finalized.pk).update(
            status=Sale.Status.COMPLETED, finalized_at=late_utc, sale_date=None
        )

        migration.backfill_sale_date(apps, None)

        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        with connection.schema_editor() as editor:
            editor.add_constraint(Sale, constraint)

        finalized.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(str(finalized.sale_date), "2026-11-09")
        self.assertIsNone(draft.sale_date)
