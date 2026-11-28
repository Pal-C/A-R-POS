"""Concurrency-sensitive paths: order numbering and payments (SC-002, US3)."""

import threading
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase

from sales.models import Payment
from sales.selectors import net_paid_expression
from stringing.models import StringingOrder
from stringing.services import create_stringing_order, record_order_payment
from stringing.tests.factories import make_order, make_user


def race(*funcs):
    """Runs each function in its own thread, released together.
    Returns a list of "ok" or exception class names."""
    barrier = threading.Barrier(len(funcs))
    outcomes = [None] * len(funcs)

    def run(index, func):
        try:
            barrier.wait(timeout=5)
            func()
            outcomes[index] = "ok"
        except Exception as exc:  # noqa: BLE001 - outcomes are asserted by callers
            outcomes[index] = type(exc).__name__
        finally:
            connection.close()

    threads = [
        threading.Thread(target=run, args=(i, func)) for i, func in enumerate(funcs)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    return outcomes


class OrderNumberConcurrencyTests(TransactionTestCase):
    def test_parallel_creates_get_distinct_numbers(self):
        user = make_user()

        def create():
            create_stringing_order(
                user=user,
                racket_description="R",
                string_type="S",
                service_price=Decimal("100.00"),
            )

        outcomes = race(*[create] * 8)
        self.assertEqual(outcomes, ["ok"] * 8)
        numbers = list(StringingOrder.objects.values_list("order_number", flat=True))
        self.assertEqual(len(numbers), 8)
        self.assertEqual(len(set(numbers)), 8)


class PaymentConcurrencyTests(TransactionTestCase):
    def test_parallel_receipts_never_exceed_total(self):
        user = make_user()
        order = make_order(user)  # total 400

        def pay():
            record_order_payment(
                order_id=order.pk,
                user=user,
                amount=Decimal("300.00"),
                payment_method=Payment.Method.CASH,
            )

        outcomes = race(pay, pay)
        self.assertEqual(sorted(outcomes), ["ValidationError", "ok"])
        net = Payment.objects.filter(stringing_order=order).aggregate(
            net=net_paid_expression()
        )["net"]
        self.assertEqual(net, Decimal("300.00"))


class IdempotentCreateConcurrencyTests(TransactionTestCase):
    def test_same_key_creates_one_order(self):
        import uuid

        from django.db import transaction

        from stringing.services import take_in_order

        user = make_user()
        key = uuid.uuid4()

        def create():
            with transaction.atomic():
                take_in_order(
                    user=user,
                    racket_description="R",
                    string_type="S",
                    service_price=Decimal("100.00"),
                    client_transaction_id=key,
                )

        outcomes = race(create, create)
        # The loser either sees the winner's order or hits the unique key;
        # the view turns that IntegrityError into the existing order.
        self.assertIn("ok", outcomes)
        self.assertTrue(set(outcomes) <= {"ok", "IntegrityError"})
        self.assertEqual(
            StringingOrder.objects.filter(client_transaction_id=key).count(), 1
        )
