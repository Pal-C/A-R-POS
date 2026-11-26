"""The shared net-paid rule matches Sale.amount_paid for every payment mix."""

from decimal import Decimal

from django.test import TestCase

from customers.tests.factories import make_customer, make_preorder, make_stringing_order
from sales.models import Payment, Sale
from sales.selectors import net_paid_expression, net_paid_subquery
from sales.services import (
    create_draft_sale,
    finalize_sale,
    process_refund,
    record_payment,
)
from sales.tests.factories import line, make_product, make_user

D = Decimal


class NetPaidTests(TestCase):
    def setUp(self):
        self.user = make_user()
        product = make_product(stock_quantity=100)

        def sale():
            draft = create_draft_sale(user=self.user, items=[line(product, 1)])
            return finalize_sale(draft.pk, self.user)  # total 1500

        def pay(target, amount, **kwargs):
            return record_payment(
                user=self.user,
                amount=D(amount),
                payment_method=Payment.Method.CASH,
                **kwargs,
                **target,
            )

        self.pay = pay
        self.unpaid = sale()

        self.partly = sale()
        pay({"sale": self.partly}, "400.00")

        self.refunded = sale()
        pay({"sale": self.refunded}, "1500.00")
        process_refund(
            user=self.user,
            sale=self.refunded,
            amount=D("300.00"),
            payment_method=Payment.Method.CASH,
            reason="Overcharge",
        )

        self.voided = sale()
        voided = pay({"sale": self.voided}, "1000.00")
        pay({"sale": self.voided}, "200.00")
        Payment.objects.filter(pk=voided.pk).update(status=Payment.Status.VOIDED)

        self.sales = [self.unpaid, self.partly, self.refunded, self.voided]

    def test_subquery_matches_property(self):
        annotated = {
            sale.pk: sale.net_paid
            for sale in Sale.objects.annotate(net_paid=net_paid_subquery("sale"))
        }
        for sale in self.sales:
            with self.subTest(sale=sale.pk):
                sale.refresh_from_db()
                self.assertEqual(annotated[sale.pk], sale.amount_paid)
        self.assertEqual(annotated[self.unpaid.pk], D("0.00"))
        self.assertEqual(annotated[self.refunded.pk], D("1200.00"))
        self.assertEqual(annotated[self.voided.pk], D("200.00"))

    def test_aggregate_matches_sum_of_properties(self):
        total = Payment.objects.filter(sale__in=self.sales).aggregate(
            paid=net_paid_expression()
        )["paid"]
        expected = sum((Sale.objects.get(pk=s.pk).amount_paid for s in self.sales), D(0))
        self.assertEqual(total, expected)
        self.assertEqual(total, D("1800.00"))

    def test_aggregate_with_prefix_and_empty_set(self):
        paid = Sale.objects.filter(pk=self.partly.pk).aggregate(
            paid=net_paid_expression(prefix="payments__")
        )["paid"]
        self.assertEqual(paid, D("400.00"))

        none = Payment.objects.none().aggregate(paid=net_paid_expression())["paid"]
        self.assertEqual(none, D("0.00"))

    def test_subquery_for_stringing_orders_and_preorders(self):
        from preorders.models import PreOrder
        from stringing.models import StringingOrder

        customer = make_customer()
        order = make_stringing_order(customer, self.user)
        preorder = make_preorder(customer, self.user)
        self.pay({"stringing_order": order}, "450.00")
        self.pay({"preorder": preorder}, "2000.00")

        self.assertEqual(
            StringingOrder.objects.annotate(p=net_paid_subquery("stringing_order"))
            .get(pk=order.pk)
            .p,
            D("450.00"),
        )
        self.assertEqual(
            PreOrder.objects.annotate(p=net_paid_subquery("preorder")).get(pk=preorder.pk).p,
            D("2000.00"),
        )
