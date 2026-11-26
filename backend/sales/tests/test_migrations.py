"""Data migration 0005 grants record_payment to existing active users."""

from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import Permission
from django.test import TestCase

from sales.tests.factories import make_user

migration = import_module("sales.migrations.0005_grant_record_payment")


class GrantRecordPaymentMigrationTests(TestCase):
    def test_grants_active_users_only_and_is_idempotent(self):
        active = make_user()
        inactive = make_user(is_active=False)

        migration.grant_record_payment(apps, None)
        migration.grant_record_payment(apps, None)

        active = type(active).objects.get(pk=active.pk)
        inactive = type(inactive).objects.get(pk=inactive.pk)
        self.assertTrue(active.has_perm("sales.record_payment"))
        self.assertFalse(
            inactive.user_permissions.filter(codename="record_payment").exists()
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type__app_label="sales", codename="record_payment"
            ).count(),
            1,
        )
