"""Search (US5), per-product summary (US3) and history (US6)."""

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from preorders.models import PreOrder
from preorders.selectors import (
    preorder_history,
    product_preorder_summary,
    search_preorders,
    store_today,
)
from preorders.services import (
    cancel_preorder,
    change_status,
    mark_product_arrived,
    update_preorder,
)
from preorders.tests.factories import (
    make_customer,
    make_payment,
    make_preorder,
    make_product,
    make_user,
)
from sales.models import Payment

S = PreOrder.Status
MANILA = ZoneInfo("Asia/Manila")


def move(preorder, *statuses):
    for status in statuses:
        change_status(
            preorder_id=preorder.pk, user=preorder.created_by, to_status=status
        )
    preorder.refresh_from_db()
    return preorder


class SearchPreOrdersTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.ana = make_customer(full_name="Ana Reyes", phone_number="0917 123 4567")
        self.ben = make_customer(full_name="Ben Cruz", phone_number="0918-555-0000")
        self.astrox = make_product(name="Astrox 100ZZ", sku="RKT-AX100")
        self.arc = make_product(name="Arcsaber 11 Pro", sku="RKT-ARC11")
        today = store_today()
        self.a = make_preorder(
            self.user,
            customer=self.ana,
            product=self.astrox,
            expected_arrival_date=today + timedelta(days=10),
        )
        self.b = make_preorder(
            self.user,
            customer=self.ben,
            product=self.arc,
            expected_arrival_date=today + timedelta(days=3),
        )
        self.c = make_preorder(self.user, customer=self.ben, product=self.astrox)

    def ids(self, **params):
        return set(search_preorders(params).values_list("pk", flat=True))

    def test_search_fields(self):
        self.assertEqual(self.ids(search=self.b.order_number[-5:]), {self.b.pk})
        self.assertEqual(self.ids(search="ana re"), {self.a.pk})
        self.assertEqual(self.ids(search="arcsaber"), {self.b.pk})
        self.assertEqual(self.ids(search="rkt-ax"), {self.a.pk, self.c.pk})

    def test_search_by_phone_any_format(self):
        for query in ("09171234567", "+63 917 123 4567", "4567"):
            with self.subTest(query=query):
                self.assertEqual(self.ids(search=query), {self.a.pk})

    def test_status_filter(self):
        move(self.a, S.ORDERED)
        cancel_preorder(preorder_id=self.b.pk, user=self.user, reason="x")
        self.assertEqual(self.ids(status="ORDERED"), {self.a.pk})
        self.assertEqual(self.ids(status="ordered,CANCELLED"), {self.a.pk, self.b.pk})

    def test_payment_state_filter_excludes_cancelled(self):
        make_payment(self.a, "1000.00")
        make_payment(self.b, "10000.00")
        make_payment(self.c, "500.00")
        cancel_preorder(preorder_id=self.c.pk, user=self.user, reason="x")
        self.assertEqual(self.ids(payment_state="PARTIAL"), {self.a.pk})
        self.assertEqual(self.ids(payment_state="paid"), {self.b.pk})
        self.assertEqual(self.ids(payment_state="UNPAID"), set())

    def test_customer_and_product_filters(self):
        self.assertEqual(self.ids(customer=str(self.ben.pk)), {self.b.pk, self.c.pk})
        self.assertEqual(self.ids(product=str(self.astrox.pk)), {self.a.pk, self.c.pk})
        self.assertEqual(
            self.ids(customer=str(self.ben.pk), product=str(self.astrox.pk)),
            {self.c.pk},
        )

    def test_expected_arrival_range(self):
        today = store_today()
        self.assertEqual(
            self.ids(
                expected_from=(today + timedelta(days=3)).isoformat(),
                expected_to=(today + timedelta(days=3)).isoformat(),
            ),
            {self.b.pk},
        )

    def test_overdue(self):
        past = store_today() - timedelta(days=1)
        PreOrder.objects.filter(pk__in=[self.a.pk, self.b.pk]).update(
            expected_arrival_date=past
        )
        move(self.b, S.ORDERED, S.ARRIVED)  # arrived: no longer overdue
        self.assertEqual(self.ids(overdue="true"), {self.a.pk})
        self.assertEqual(self.ids(overdue="false"), {self.b.pk, self.c.pk})
        self.assertTrue(search_preorders({}).get(pk=self.a.pk).is_overdue)

    def test_orderings(self):
        newest = list(search_preorders({}).values_list("pk", flat=True))
        self.assertEqual(newest, [self.c.pk, self.b.pk, self.a.pk])
        by_date = list(
            search_preorders({"ordering": "expected_arrival_date"}).values_list(
                "pk", flat=True
            )
        )
        self.assertEqual(by_date, [self.b.pk, self.a.pk, self.c.pk])  # nulls last

    def test_invalid_values(self):
        cases = {
            "status": "DONE",
            "payment_state": "SOME",
            "customer": "abc",
            "product": "²",
            "expected_from": "2026-13-01",
            "overdue": "maybe",
            "ordering": "price",
        }
        for param, value in cases.items():
            with self.subTest(param=param), self.assertRaises(ValidationError) as ctx:
                search_preorders({param: value})
            self.assertIn(param, ctx.exception.message_dict)


class ProductSummaryTests(TestCase):
    def test_counts_units_and_ordered_list(self):
        user = make_user()
        product = make_product()
        make_preorder(user, product=product, quantity=1)  # pending
        first = move(make_preorder(user, product=product, quantity=2), S.ORDERED)
        second = move(make_preorder(user, product=product, quantity=1), S.ORDERED)
        move(make_preorder(user, product=product, quantity=4), S.ORDERED, S.ARRIVED)
        cancel_preorder(
            preorder_id=make_preorder(user, product=product).pk, user=user, reason="x"
        )
        make_preorder(user)  # another product

        with CaptureQueriesContext(connection) as ctx:
            summary = product_preorder_summary(product)
        self.assertEqual(len(ctx.captured_queries), 2)
        self.assertEqual(
            summary["waiting"],
            {
                S.PENDING: {"orders": 1, "units": 1},
                S.ORDERED: {"orders": 2, "units": 3},
                S.ARRIVED: {"orders": 1, "units": 4},
            },
        )
        self.assertEqual(
            [o.pk for o in summary["ordered_preorders"]], [first.pk, second.pk]
        )


class HistoryTests(TestCase):
    def test_events_and_payments_merged_in_time_order(self):
        user = make_user()
        preorder = make_preorder(user)
        make_payment(preorder, "4000.00")
        move(preorder, S.ORDERED)
        mark_product_arrived(
            product_id=preorder.product_id, received_quantity=5, user=user
        )
        update_preorder(preorder_id=preorder.pk, user=user, notes="Call first")
        cancel_preorder(preorder_id=preorder.pk, user=user, reason="Changed mind")

        history = preorder_history(preorder)
        self.assertEqual(
            [e["type"] for e in history],
            [
                "CREATED",
                "PAYMENT",
                "STATUS_CHANGED",
                "STATUS_CHANGED",
                "UPDATED",
                "CANCELLED",
            ],
        )
        self.assertEqual(history[1]["amount"], "4000.00")
        self.assertEqual(history[3]["to_status"], S.ARRIVED)
        self.assertEqual(history[3]["arrival"], {"received_quantity": 5})
        self.assertEqual(history[4]["changes"], {"notes": ["", "Call first"]})
        self.assertEqual(history[5]["reason"], "Changed mind")

    def test_payment_uses_payment_date(self):
        user = make_user()
        preorder = make_preorder(user)
        payment = make_payment(preorder, "100.00")
        backdated = datetime(2026, 1, 5, 9, 0, tzinfo=MANILA)
        Payment.objects.filter(pk=payment.pk).update(payment_date=backdated)
        history = preorder_history(preorder)
        self.assertEqual(history[0]["type"], "PAYMENT")
        self.assertEqual(history[0]["at"], backdated)
        self.assertEqual(Decimal(history[0]["amount"]), Decimal("100.00"))
