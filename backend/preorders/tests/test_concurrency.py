"""Concurrency-sensitive paths: numbering, receipts, arrivals (SC-002)."""

import threading
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase

from preorders.models import PreOrder
from preorders.services import (
    change_status,
    create_preorder,
    mark_product_arrived,
    record_preorder_payment,
)
from preorders.tests.factories import (
    make_customer,
    make_preorder,
    make_product,
    make_user,
)
from sales.models import Payment
from sales.selectors import net_paid_expression


def race(*funcs):
    """Runs each function in its own thread, released together.
    Returns a list of "ok" or exception class names, plus the results."""
    barrier = threading.Barrier(len(funcs))
    outcomes = [None] * len(funcs)
    results = [None] * len(funcs)

    def run(index, func):
        try:
            barrier.wait(timeout=5)
            results[index] = func()
            outcomes[index] = "ok"
        except Exception as exc:  # noqa: BLE001 - outcomes are asserted by callers
            outcomes[index] = type(exc).__name__
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i, f)) for i, f in enumerate(funcs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    return outcomes, results


class PreOrderConcurrencyTests(TransactionTestCase):
    def test_parallel_creates_get_distinct_numbers(self):
        user = make_user()
        customer = make_customer()
        product = make_product()

        def create():
            return create_preorder(
                user=user, customer=customer, product=product, quantity=1
            )

        outcomes, _ = race(*[create] * 8)
        self.assertEqual(outcomes, ["ok"] * 8)
        numbers = list(PreOrder.objects.values_list("order_number", flat=True))
        self.assertEqual(len(set(numbers)), 8)

    def test_parallel_receipts_never_exceed_total(self):
        user = make_user()
        preorder = make_preorder(user)  # 10000

        def pay():
            return record_preorder_payment(
                preorder_id=preorder.pk,
                user=user,
                amount=Decimal("6000.00"),
                payment_method=Payment.Method.CASH,
            )

        outcomes, _ = race(pay, pay)
        self.assertEqual(sorted(outcomes), ["ValidationError", "ok"])
        net = Payment.objects.filter(preorder=preorder).aggregate(
            net=net_paid_expression()
        )["net"]
        self.assertEqual(net, Decimal("6000.00"))

    def test_parallel_arrivals_mark_an_order_once(self):
        user = make_user()
        product = make_product()
        preorder = make_preorder(user, product=product, quantity=1)
        change_status(
            preorder_id=preorder.pk, user=user, to_status=PreOrder.Status.ORDERED
        )

        def arrive():
            return mark_product_arrived(
                product_id=product.pk, received_quantity=1, user=user
            )

        outcomes, results = race(arrive, arrive)
        self.assertEqual(outcomes, ["ok", "ok"])
        marked = sorted(len(result["marked"]) for result in results)
        self.assertEqual(marked, [0, 1])
        self.assertEqual(
            preorder.events.filter(to_status=PreOrder.Status.ARRIVED).count(), 1
        )
