from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import TestCase

from customers.models import Customer


class CustomerModelTests(TestCase):
    def test_blank_full_name_is_rejected_by_database(self):
        for name in ("", "   ", "\t"):
            with self.subTest(name=repr(name)):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Customer.objects.create(full_name=name)

    def test_phone_normalized_tracks_phone_number(self):
        customer = Customer.objects.create(
            full_name="Ana", phone_number="+63 917 123 4567"
        )
        self.assertEqual(customer.phone_normalized, "09171234567")

        customer.phone_number = "(02) 8123 4567"
        customer.save(update_fields=["phone_number"])
        customer.refresh_from_db()
        self.assertEqual(customer.phone_normalized, "0281234567")

        customer.phone_number = ""
        customer.save()
        customer.refresh_from_db()
        self.assertEqual(customer.phone_normalized, "")

    def test_archive_permission_is_registered(self):
        self.assertTrue(
            Permission.objects.filter(
                content_type__app_label="customers", codename="archive_customer"
            ).exists()
        )
