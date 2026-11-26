"""Database constraints on sales models reject invalid rows directly."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from sales.models import Payment, Sale, SaleItem
from sales.tests.factories import make_product, make_user

D = Decimal


class SalesConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        self.sale = Sale.objects.create(
            created_by=self.user,
            subtotal=D("100.00"),
            total_amount=D("100.00"),
        )

    def assert_rejected(self, model, **values):
        with self.assertRaises(IntegrityError), transaction.atomic():
            model.objects.create(**values)

    def test_sale_constraints(self):
        base = {"created_by": self.user}
        cases = {
            "negative subtotal": dict(subtotal=D("-1")),
            "negative discount": dict(subtotal=D("10"), discount_amount=D("-1")),
            "negative total": dict(total_amount=D("-1")),
            "discount above subtotal": dict(subtotal=D("10"), discount_amount=D("11")),
        }
        for name, values in cases.items():
            with self.subTest(name):
                self.assert_rejected(Sale, **base, **values)

    def test_sale_item_constraints(self):
        base = {
            "sale": self.sale,
            "product": self.product,
            "quantity": 1,
            "unit_selling_price": D("100"),
            "unit_cost_price": D("50"),
        }
        cases = {
            "zero quantity": dict(quantity=0),
            "negative selling price": dict(unit_selling_price=D("-1")),
            "negative cost price": dict(unit_cost_price=D("-1")),
            "negative discount": dict(discount_amount=D("-1")),
            "discount above line": dict(quantity=2, discount_amount=D("200.01")),
        }
        for name, values in cases.items():
            with self.subTest(name):
                self.assert_rejected(SaleItem, **{**base, **values})

    def test_payment_constraints(self):
        base = {
            "sale": self.sale,
            "amount": D("10"),
            "payment_method": Payment.Method.CASH,
            "received_by": self.user,
        }
        cases = {
            "zero amount": dict(amount=D("0")),
            "no order": dict(sale=None),
        }
        for name, values in cases.items():
            with self.subTest(name):
                self.assert_rejected(Payment, **{**base, **values})

    def test_payment_cannot_belong_to_two_orders(self):
        from preorders.models import PreOrder
        from sales.tests.factories import make_customer

        preorder = PreOrder.objects.create(
            order_number="PO-1",
            customer=make_customer(),
            product=self.product,
            quantity=1,
            agreed_unit_price=D("100"),
            created_by=self.user,
        )
        self.assert_rejected(
            Payment,
            sale=self.sale,
            preorder=preorder,
            amount=D("10"),
            payment_method=Payment.Method.CASH,
            received_by=self.user,
        )

    def test_sale_permissions_are_registered(self):
        from django.contrib.auth.models import Permission

        codenames = set(
            Permission.objects.filter(content_type__app_label="sales").values_list(
                "codename", flat=True
            )
        )
        self.assertLessEqual(
            {
                "finalize_sale",
                "cancel_sale",
                "apply_sale_discount",
                "view_sales_reports",
                "record_payment",
                "process_refund",
            },
            codenames,
        )
