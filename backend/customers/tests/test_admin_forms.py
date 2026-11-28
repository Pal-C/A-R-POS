"""Stringing and pre-order admin forms refuse newly chosen archived customers."""

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from customers.services import archive_customer
from customers.tests.factories import (
    make_customer,
    make_preorder,
    make_stringing_order,
    make_user,
)
from preorders.admin import PreOrderAdmin
from preorders.models import PreOrder
from sales.tests.factories import make_product
from stringing.admin import StringingOrderAdmin
from stringing.models import StringingOrder


class AdminCustomerGuardTests(TestCase):
    def setUp(self):
        self.user = make_user(is_staff=True, is_superuser=True)
        self.request = RequestFactory().post("/")
        self.request.user = self.user
        self.active = make_customer(full_name="Active")
        self.archived = make_customer(full_name="Archived")
        archive_customer(self.archived.pk, self.user)

    def form_for(self, admin_class, model, instance, data):
        model_admin = admin_class(model, AdminSite())
        form_class = model_admin.get_form(self.request, instance)
        return form_class(data=data, instance=instance)

    def stringing_data(self, customer, **overrides):
        data = {
            "order_number": "STR-ADMIN",
            "customer": customer.pk,
            "racket_description": "Racket",
            "string_type": "BG66",
            "tension": "26",
            "service_price": "450.00",
            "discount_amount": "0",
            "direct_cost": "0",
            "stencil_price": "0",
            "grip_price": "0",
            "status": StringingOrder.Status.RECEIVED,
            "created_by": self.user.pk,
            "cancellation_reason": "",
        }
        data.update(overrides)
        return data

    def preorder_data(self, customer, product, **overrides):
        data = {
            "order_number": "PO-ADMIN",
            "customer": customer.pk,
            "product": product.pk,
            "quantity": 1,
            "agreed_unit_price": "5000.00",
            "status": PreOrder.Status.PENDING,
            "created_by": self.user.pk,
        }
        data.update(overrides)
        return data

    def test_new_orders_refuse_archived_customer(self):
        product = make_product()
        cases = [
            (StringingOrderAdmin, StringingOrder, self.stringing_data),
            (PreOrderAdmin, PreOrder, lambda c: self.preorder_data(c, product)),
        ]
        for admin_class, model, data in cases:
            with self.subTest(model.__name__):
                form = self.form_for(admin_class, model, None, data(self.archived))
                self.assertFalse(form.is_valid())
                self.assertIn("customer", form.errors)

                form = self.form_for(admin_class, model, None, data(self.active))
                self.assertTrue(form.is_valid(), form.errors)

    def test_existing_orders_with_later_archived_customer_can_still_be_edited(self):
        customer = make_customer(full_name="Later archived")
        order = make_stringing_order(customer, self.user, order_number="STR-OLD")
        preorder = make_preorder(customer, self.user, order_number="PO-OLD")
        archive_customer(customer.pk, self.user)

        form = self.form_for(
            StringingOrderAdmin,
            StringingOrder,
            order,
            self.stringing_data(customer, order_number="STR-OLD", tension="28"),
        )
        self.assertTrue(form.is_valid(), form.errors)

        form = self.form_for(
            PreOrderAdmin,
            PreOrder,
            preorder,
            self.preorder_data(customer, preorder.product, order_number="PO-OLD"),
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_switching_existing_order_to_archived_customer_is_refused(self):
        order = make_stringing_order(self.active, self.user, order_number="STR-SW")
        form = self.form_for(
            StringingOrderAdmin,
            StringingOrder,
            order,
            self.stringing_data(self.archived, order_number="STR-SW"),
        )
        self.assertFalse(form.is_valid())
