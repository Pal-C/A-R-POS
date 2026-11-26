from django.core.exceptions import ValidationError
from django.test import TestCase

from customers.models import Customer
from customers.services import create_customer
from customers.tests.factories import make_customer


class CreateCustomerTests(TestCase):
    def test_creates_active_customer_with_name_only(self):
        customer = create_customer(full_name="  Ana Reyes  ")

        self.assertEqual(customer.full_name, "Ana Reyes")
        self.assertTrue(customer.is_active)
        self.assertEqual(customer.phone_number, "")

    def test_creates_customer_with_all_fields(self):
        customer = create_customer(
            full_name="Ana Reyes",
            phone_number=" 0917 123 4567 ",
            email=" ana@example.com ",
            address="Quezon City",
            notes="Prefers 26 lbs",
        )
        self.assertEqual(customer.phone_number, "0917 123 4567")
        self.assertEqual(customer.phone_normalized, "09171234567")
        self.assertEqual(customer.email, "ana@example.com")

    def test_rejections(self):
        cases = {
            "blank name": dict(full_name=""),
            "whitespace name": dict(full_name="   "),
            "missing name": dict(),
            "name too long": dict(full_name="x" * 151),
            "bad email": dict(full_name="Ana", email="not-an-email"),
            "bad phone characters": dict(full_name="Ana", phone_number="0917-abc"),
            "phone too long": dict(full_name="Ana", phone_number="1" * 31),
        }
        for name, fields in cases.items():
            with self.subTest(name), self.assertRaises(ValidationError):
                create_customer(**fields)

        self.assertEqual(Customer.objects.count(), 0)

    def test_errors_are_keyed_by_field(self):
        with self.assertRaises(ValidationError) as ctx:
            create_customer(full_name=" ", email="bad")
        self.assertEqual(set(ctx.exception.message_dict), {"full_name", "email"})

    def test_duplicate_phone_is_allowed(self):
        make_customer(full_name="Parent", phone_number="09171234567")
        child = create_customer(full_name="Child", phone_number="+63 917 123 4567")
        self.assertEqual(child.phone_normalized, "09171234567")


class UpdateCustomerTests(TestCase):
    def setUp(self):
        from customers.services import update_customer

        self.update = update_customer
        self.customer = make_customer(
            full_name="Ana Reyes", phone_number="0917 123 4567", email="ana@example.com"
        )

    def test_partial_update_recomputes_phone(self):
        customer = self.update(self.customer.pk, phone_number="+63 918 000 1111")

        self.assertEqual(customer.full_name, "Ana Reyes")
        self.assertEqual(customer.email, "ana@example.com")
        self.assertEqual(customer.phone_normalized, "09180001111")

    def test_rejected_update_leaves_row_unchanged(self):
        for fields in ({"full_name": " "}, {"email": "bad"}, {"phone_number": "x1"}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                self.update(self.customer.pk, **fields)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, "Ana Reyes")
        self.assertEqual(self.customer.email, "ana@example.com")

    def test_cannot_change_archive_status(self):
        with self.assertRaises(ValidationError):
            self.update(self.customer.pk, is_active=False)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

    def test_archived_customer_can_be_edited(self):
        Customer.objects.filter(pk=self.customer.pk).update(is_active=False)
        customer = self.update(self.customer.pk, notes="Moved away")
        self.assertEqual(customer.notes, "Moved away")
        self.assertFalse(customer.is_active)

    def test_last_save_wins_with_complete_values(self):
        self.update(self.customer.pk, full_name="First Edit", notes="first")
        self.update(self.customer.pk, full_name="Second Edit", notes="second")

        self.customer.refresh_from_db()
        self.assertEqual(
            (self.customer.full_name, self.customer.notes), ("Second Edit", "second")
        )

    def test_unknown_customer(self):
        with self.assertRaises(Customer.DoesNotExist):
            self.update(999999, notes="x")


# ---------------------------------------------------------------------------
# US5: archive, reactivate, delete
# ---------------------------------------------------------------------------


class ArchiveLifecycleTests(TestCase):
    def setUp(self):
        from customers.tests.factories import make_user

        self.manager = make_user()
        self.customer = make_customer(full_name="Ana Reyes")

    def test_archive_and_reactivate_write_audit_events(self):
        from customers.models import CustomerAuditEvent
        from customers.services import archive_customer, reactivate_customer

        archived = archive_customer(self.customer.pk, self.manager)
        self.assertFalse(archived.is_active)

        reactivated = reactivate_customer(self.customer.pk, self.manager)
        self.assertTrue(reactivated.is_active)

        events = list(
            CustomerAuditEvent.objects.order_by("id").values_list(
                "action", "customer_ref", "customer_name", "performed_by"
            )
        )
        self.assertEqual(
            events,
            [
                ("ARCHIVED", self.customer.pk, "Ana Reyes", self.manager.pk),
                ("REACTIVATED", self.customer.pk, "Ana Reyes", self.manager.pk),
            ],
        )

    def test_state_rules(self):
        from customers.services import archive_customer, reactivate_customer

        with self.assertRaises(ValidationError):
            reactivate_customer(self.customer.pk, self.manager)

        archive_customer(self.customer.pk, self.manager)
        with self.assertRaises(ValidationError):
            archive_customer(self.customer.pk, self.manager)

    def test_archiving_changes_no_transactions(self):
        from customers.services import archive_customer, reactivate_customer
        from customers.tests.factories import (
            make_finalized_sale,
            make_preorder,
            make_stringing_order,
        )
        from preorders.models import PreOrder
        from sales.models import Payment, Sale
        from stringing.models import StringingOrder

        make_finalized_sale(self.customer, self.manager, paid="100.00")
        make_stringing_order(self.customer, self.manager)
        make_preorder(self.customer, self.manager)

        def snapshot():
            return [
                list(model.objects.order_by("pk").values())
                for model in (Sale, StringingOrder, PreOrder, Payment)
            ]

        before = snapshot()
        archive_customer(self.customer.pk, self.manager)
        reactivate_customer(self.customer.pk, self.manager)
        self.assertEqual(snapshot(), before)

    def test_ensure_usable(self):
        from customers.services import archive_customer, ensure_usable

        ensure_usable(self.customer)
        ensure_usable(None)  # walk-in
        archive_customer(self.customer.pk, self.manager)
        self.customer.refresh_from_db()
        with self.assertRaises(ValidationError):
            ensure_usable(self.customer)


class DeleteCustomerTests(TestCase):
    def setUp(self):
        from customers.tests.factories import make_user

        self.manager = make_user()

    def test_deletes_customer_without_history_and_keeps_audit(self):
        from customers.models import CustomerAuditEvent
        from customers.services import archive_customer, delete_customer

        customer = make_customer(full_name="Typo Customer")
        archive_customer(customer.pk, self.manager)  # archived customers too
        customer_id = customer.pk

        delete_customer(customer_id, self.manager)

        self.assertFalse(Customer.objects.filter(pk=customer_id).exists())
        event = CustomerAuditEvent.objects.get(action="DELETED")
        self.assertEqual(
            (event.customer_ref, event.customer_name, event.performed_by),
            (customer_id, "Typo Customer", self.manager),
        )

    def test_refused_for_every_kind_of_history(self):
        from customers.models import CustomerAuditEvent
        from customers.services import delete_customer
        from customers.tests.factories import (
            make_finalized_sale,
            make_preorder,
            make_stringing_order,
        )
        from sales.services import cancel_sale, create_draft_sale
        from sales.tests.factories import line, make_product
        from stringing.models import StringingOrder

        def cancelled_sale(c):
            sale = make_finalized_sale(c, self.manager)
            cancel_sale(sale_id=sale.pk, user=self.manager, reason="x")

        makers = {
            "draft sale": lambda c: create_draft_sale(
                user=self.manager, customer=c, items=[line(make_product(), 1)]
            ),
            "finalized sale": lambda c: make_finalized_sale(c, self.manager),
            "cancelled sale": cancelled_sale,
            "stringing order": lambda c: make_stringing_order(c, self.manager),
            "cancelled stringing order": lambda c: make_stringing_order(
                c, self.manager, status=StringingOrder.Status.CANCELLED
            ),
            "pre-order": lambda c: make_preorder(c, self.manager),
        }
        for name, make in makers.items():
            with self.subTest(name):
                customer = make_customer()
                make(customer)
                with self.assertRaises(ValidationError) as ctx:
                    delete_customer(customer.pk, self.manager)
                self.assertIn("Archive", str(ctx.exception))
                self.assertTrue(Customer.objects.filter(pk=customer.pk).exists())

        self.assertFalse(CustomerAuditEvent.objects.filter(action="DELETED").exists())
