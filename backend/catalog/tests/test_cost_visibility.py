"""Cost price and inventory value are visible only with catalog.view_product_cost (FR-014)."""

from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from catalog.models import Product
from catalog.tests.helpers import grant
from sales.tests.factories import make_product, make_user


class CostVisibilityTests(APITestCase):
    def setUp(self):
        self.cashier = make_user(username="cashier")
        self.manager = grant(make_user(username="manager"), "view_product_cost")
        self.product = make_product(
            cost_price=Decimal("320.00"),
            selling_price=Decimal("450.00"),
            stock_quantity=3,
        )
        make_product(
            cost_price=Decimal("100.00"), stock_quantity=2, low_stock_threshold=5
        )
        make_product(cost_price=Decimal("999.00"), stock_quantity=0)
        make_product(cost_price=Decimal("500.00"), stock_quantity=10, is_active=False)

    def get(self, user, url):
        self.client.force_authenticate(user)
        return self.client.get(url)

    def test_product_list_and_detail_hide_cost_without_permission(self):
        for url in (
            reverse("product-list"),
            reverse("product-detail", kwargs={"pk": self.product.pk}),
            reverse("inventory-low-stock"),
            reverse("inventory-out-of-stock"),
        ):
            with self.subTest(url=url):
                body = self.get(self.cashier, url).json()
                items = body.get("results", [body])
                self.assertTrue(items)
                for item in items:
                    self.assertNotIn("cost_price", item)

    def test_product_list_and_detail_show_cost_with_permission(self):
        detail = self.get(
            self.manager, reverse("product-detail", kwargs={"pk": self.product.pk})
        ).json()
        listing = self.get(self.manager, reverse("product-list")).json()

        self.assertEqual(detail["cost_price"], "320.00")
        self.assertTrue(all("cost_price" in item for item in listing["results"]))

    def test_summary_includes_inventory_value_only_with_permission(self):
        cashier = self.get(self.cashier, reverse("inventory-summary")).json()
        manager = self.get(self.manager, reverse("inventory-summary")).json()

        self.assertNotIn("inventory_value", cashier)
        # Active only: 320*3 + 100*2 + 999*0 + default factory products none.
        self.assertEqual(manager["inventory_value"], "1160.00")
        self.assertEqual(manager["active_product_count"], 3)
        self.assertEqual(manager["low_stock_count"], 2)
        self.assertEqual(manager["out_of_stock_count"], 1)
        self.assertEqual(manager["total_units_in_stock"], 5)

    def test_summary_is_one_query(self):
        self.client.force_authenticate(self.manager)
        # Warm the permission cache so only the aggregate is counted.
        self.manager.has_perm("catalog.view_product_cost")

        with self.assertNumQueries(1):
            self.client.get(reverse("inventory-summary"))

    def test_product_list_is_two_queries(self):
        self.client.force_authenticate(self.manager)
        self.manager.has_perm("catalog.view_product_cost")

        with self.assertNumQueries(2):
            self.client.get(reverse("product-list"))

    def ordered_costs(self, user):
        url = reverse("product-list") + "?ordering=-cost_price"
        names = [p["name"] for p in self.get(user, url).json()["results"]]
        costs = dict(Product.objects.values_list("name", "cost_price"))
        return names, [costs[name] for name in names]

    def test_ordering_by_cost_is_ignored_without_permission(self):
        names, _ = self.ordered_costs(self.cashier)

        # Falls back to the default ordering (by name).
        self.assertEqual(names, sorted(names))

    def test_ordering_by_cost_works_with_permission(self):
        _, costs = self.ordered_costs(self.manager)

        self.assertEqual(costs, sorted(costs, reverse=True))
