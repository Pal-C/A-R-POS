from django.core.exceptions import ValidationError
from django.test import TestCase

from customers.selectors import search_customers
from customers.tests.factories import make_customer


class SearchCustomersTests(TestCase):
    def setUp(self):
        self.ana = make_customer(full_name="Ana Reyes", phone_number="0917 123 4567")
        self.ben = make_customer(full_name="Ben Santos", phone_number="+63 918 555 0000")
        self.pena = make_customer(full_name="Carla Peña", phone_number="(02) 8123 4567")
        self.archived = make_customer(
            full_name="Ana Archived", phone_number="0917 000 0000", is_active=False
        )

    def names(self, query="", status="active"):
        return [c.full_name for c in search_customers(query, status)]

    def test_default_lists_active_customers_alphabetically(self):
        self.assertEqual(self.names(), ["Ana Reyes", "Ben Santos", "Carla Peña"])

    def test_name_search_is_partial_case_insensitive_and_trimmed(self):
        for query in ("ana", "ANA", "  reyes ", "a rey"):
            with self.subTest(query=query):
                self.assertEqual(self.names(query), ["Ana Reyes"])

    def test_accented_names_are_found(self):
        self.assertEqual(self.names("Peña"), ["Carla Peña"])

    def test_phone_search_across_formats(self):
        cases = {
            "4567": ["Ana Reyes", "Carla Peña"],
            "09171234567": ["Ana Reyes"],
            "0917-123": ["Ana Reyes"],
            "+63 917": ["Ana Reyes"],
            "+63 918 555 0000": ["Ben Santos"],
            "(02) 8123": ["Carla Peña"],
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(self.names(query), expected)

    def test_status_filter(self):
        self.assertEqual(self.names("ana", "archived"), ["Ana Archived"])
        self.assertEqual(self.names("ana", "all"), ["Ana Archived", "Ana Reyes"])

    def test_ties_are_ordered_by_id(self):
        twin = make_customer(full_name="Ana Reyes")
        self.assertEqual(
            [c.pk for c in search_customers("Ana Reyes", "active")],
            [self.ana.pk, twin.pk],
        )

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValidationError):
            search_customers("", "deleted")


class PhoneMatchesTests(TestCase):
    def setUp(self):
        self.ana = make_customer(full_name="Ana", phone_number="0917 123 4567")

    def test_matches_on_normalized_phone(self):
        from customers.selectors import phone_matches

        self.assertEqual(list(phone_matches("+63 917-123-4567")), [self.ana])

    def test_active_only_exact_and_limited(self):
        from customers.selectors import phone_matches

        make_customer(full_name="Archived", phone_number="09171234567", is_active=False)
        make_customer(full_name="Partial", phone_number="0917 123")
        for i in range(6):
            make_customer(full_name=f"Family {i}", phone_number="09171234567")

        matches = list(phone_matches("09171234567"))
        self.assertEqual(len(matches), 5)
        self.assertTrue(all(c.is_active for c in matches))
        self.assertNotIn("Partial", [c.full_name for c in matches])

    def test_exclude_id_and_empty_input(self):
        from customers.selectors import phone_matches

        self.assertEqual(list(phone_matches("09171234567", exclude_id=self.ana.pk)), [])
        for value in ("", None, "abc", "   "):
            with self.subTest(value=value):
                self.assertEqual(list(phone_matches(value)), [])


class CustomerSummaryTests(TestCase):
    """Summary totals checked against hand-computed values (data-model.md)."""

    def setUp(self):
        from decimal import Decimal

        from customers.tests.factories import (
            make_finalized_sale,
            make_preorder,
            make_stringing_order,
            make_user,
        )
        from preorders.models import PreOrder
        from sales.models import Payment
        from sales.services import cancel_sale, create_draft_sale, process_refund
        from sales.services import record_payment as pay
        from sales.tests.factories import line, make_product
        from stringing.models import StringingOrder

        D = Decimal
        self.D = D
        user = make_user()
        self.customer = make_customer()
        racket = make_product(selling_price=D("1500.00"), stock_quantity=50)

        # Sale A: 1500, paid 1500, refunded 200 -> net 1300, balance 200
        a = make_finalized_sale(self.customer, user, items=[line(racket, 1)], paid="1500.00")
        process_refund(
            user=user, sale=a, amount=D("200.00"),
            payment_method=Payment.Method.CASH, reason="Adjustment",
        )
        # Sale B: 3000, paid 1000 -> balance 2000
        make_finalized_sale(self.customer, user, items=[line(racket, 2)], paid="1000.00")
        # Sale C: cancelled after 500 paid -> counted, adds nothing
        c = make_finalized_sale(self.customer, user, items=[line(racket, 1)], paid="500.00")
        cancel_sale(sale_id=c.pk, user=user, reason="Changed mind")
        # Draft: excluded entirely
        create_draft_sale(user=user, customer=self.customer, items=[line(racket, 1)])

        # Stringing: 450 - 50 = 400 unpaid (unfinished); 300 completed and paid
        make_stringing_order(
            self.customer, user, service_price=D("450.00"), discount_amount=D("50.00")
        )
        done = make_stringing_order(
            self.customer, user, service_price=D("300.00"),
            status=StringingOrder.Status.COMPLETED,
        )
        pay(user=user, stringing_order=done, amount=D("300.00"),
            payment_method=Payment.Method.CASH)
        # A refund after pickup does not reopen a balance (stringing FR-028).
        process_refund(
            user=user, stringing_order=done, amount=D("20.00"),
            payment_method=Payment.Method.CASH, reason="Goodwill",
        )
        # Cancelled stringing order: counted, adds nothing
        make_stringing_order(
            self.customer, user, status=StringingOrder.Status.CANCELLED
        )

        # Pre-order: 2 x 5000 = 10000, deposit 4000 -> balance 6000 (open)
        po = make_preorder(self.customer, user, quantity=2)
        pay(user=user, preorder=po, amount=D("4000.00"),
            payment_method=Payment.Method.GCASH)
        # Fulfilled pre-order refunded after handover: settled, adds nothing.
        done_po = make_preorder(
            self.customer, user, quantity=1, agreed_unit_price=D("1000.00")
        )
        pay(user=user, preorder=done_po, amount=D("1000.00"),
            payment_method=Payment.Method.CASH)
        PreOrder.objects.filter(pk=done_po.pk).update(
            status=PreOrder.Status.FULFILLED,
            fulfilled_at=done_po.created_at,
            fulfilled_by=user,
            settled_at=done_po.created_at,
        )
        process_refund(
            user=user, preorder=done_po, amount=D("100.00"),
            payment_method=Payment.Method.CASH, reason="Goodwill",
        )

        # Another customer's records must not leak in.
        make_finalized_sale(make_customer(), user, paid="100.00")

    def test_summary_totals(self):
        from customers.selectors import customer_summary

        D = self.D
        self.assertEqual(
            customer_summary(self.customer),
            {
                "sales_count": 3,
                "stringing_orders_count": 3,
                "preorders_count": 2,
                "total_spent": D("2300.00"),
                "outstanding_balance": D("8600.00"),
                "open_preorders_count": 1,
                "unfinished_stringing_orders_count": 1,
            },
        )

    def test_customer_without_history_gets_zeros(self):
        from customers.selectors import customer_summary

        summary = customer_summary(make_customer())
        self.assertEqual(summary["total_spent"], self.D("0.00"))
        self.assertEqual(summary["outstanding_balance"], self.D("0.00"))
        self.assertEqual(
            (summary["sales_count"], summary["stringing_orders_count"],
             summary["preorders_count"]),
            (0, 0, 0),
        )
