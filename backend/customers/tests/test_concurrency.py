"""Deleting a customer while a sale is attached to them never loses history."""

import threading

from django.db import connection
from django.test import TransactionTestCase

from customers.models import Customer
from customers.services import delete_customer
from customers.tests.factories import make_customer, make_user
from sales.models import Sale
from sales.services import create_draft_sale
from sales.tests.factories import line, make_product


def race(**actions):
    """Runs each named action in its own thread, released together.
    Returns {name: "ok" | exception class name}."""
    barrier = threading.Barrier(len(actions))
    outcomes = {}

    def run(name, func):
        try:
            barrier.wait(timeout=5)
            func()
            outcomes[name] = "ok"
        except Exception as exc:  # noqa: BLE001 - outcomes are asserted by callers
            outcomes[name] = type(exc).__name__
        finally:
            connection.close()

    threads = [
        threading.Thread(target=run, args=(name, func))
        for name, func in actions.items()
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    return outcomes


class DeleteRaceTests(TransactionTestCase):
    def attempt(self):
        user = make_user()
        product = make_product()
        customer = make_customer()

        outcomes = race(
            delete=lambda: delete_customer(customer.pk, user),
            attach=lambda: create_draft_sale(
                user=user, customer=customer, items=[line(product, 1)]
            ),
        )

        exists = Customer.objects.filter(pk=customer.pk).exists()
        sales = Sale.objects.filter(customer_id=customer.pk).count()

        # Exactly one side wins, and history is never orphaned.
        self.assertEqual(list(outcomes.values()).count("ok"), 1, outcomes)
        if outcomes["delete"] == "ok":
            self.assertFalse(exists)
            self.assertEqual(sales, 0)
        else:
            self.assertTrue(exists)
            self.assertEqual(sales, 1)

    def test_delete_and_attach_never_both_succeed(self):
        for attempt in range(3):
            with self.subTest(attempt=attempt):
                self.attempt()
