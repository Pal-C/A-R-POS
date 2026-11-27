"""Concurrent product edits (constitution II: concurrency-sensitive paths)."""

import threading
from decimal import Decimal

from django.db import close_old_connections
from django.test import TransactionTestCase

from catalog.models import Product, ProductEvent
from catalog.services import ProductConflict, update_product
from catalog.tests.helpers import COST, STOCK, grant
from inventory.models import InventoryMovement
from inventory.services import adjust_stock
from sales.tests.factories import make_product, make_user


def run_in_threads(*targets):
    barrier = threading.Barrier(len(targets))
    results = [None] * len(targets)

    def wrap(i, target):
        try:
            barrier.wait()
            results[i] = target()
        except Exception as exc:  # noqa: BLE001 — collected for assertions
            results[i] = exc
        finally:
            close_old_connections()

    threads = [
        threading.Thread(target=wrap, args=(i, t)) for i, t in enumerate(targets)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


class ProductConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = grant(make_user(), COST, STOCK)
        self.product = make_product(selling_price=Decimal("450.00"), stock_quantity=89)

    def edit_price(self, price):
        return lambda: update_product(
            product_id=self.product.pk,
            user=self.user,
            changes={"selling_price": Decimal(price)},
            expected={"selling_price": "450.00"},
            reason="Reprice",
        )

    def test_two_editors_of_the_same_field_one_wins_one_conflicts(self):
        results = run_in_threads(self.edit_price("480.00"), self.edit_price("470.00"))

        conflicts = [r for r in results if isinstance(r, ProductConflict)]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(ProductEvent.objects.count(), 1)

    def test_stock_edit_and_concurrent_stock_change_serialize(self):
        def edit_stock():
            return update_product(
                product_id=self.product.pk,
                user=self.user,
                changes={"stock_quantity": 100},
                expected={"stock_quantity": 89},
                reason="Delivery counted",
            )

        def sell():
            return adjust_stock(
                product_id=self.product.pk,
                quantity_change=-3,
                reason="Sold",
                created_by=self.user,
            )

        results = run_in_threads(edit_stock, sell)

        self.product.refresh_from_db()
        movements = InventoryMovement.objects.filter(product=self.product).count()
        if isinstance(results[0], ProductConflict):
            # The sale went first; the edit saw stale stock and was refused.
            self.assertEqual(self.product.stock_quantity, 86)
            self.assertEqual(movements, 1)
        else:
            self.assertNotIsInstance(results[0], Exception)
            self.assertEqual(self.product.stock_quantity, 97)
            self.assertEqual(movements, 2)
        self.assertNotIsInstance(results[1], Exception)
        self.assertEqual(
            Product.objects.get(pk=self.product.pk).stock_quantity,
            self.product.stock_quantity,
        )
