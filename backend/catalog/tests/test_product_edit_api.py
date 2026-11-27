"""Product create/edit/history API (contracts/products-api.md)."""

from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from catalog.models import Product, ProductEvent
from catalog.services import update_product
from catalog.tests.helpers import COST, STOCK, grant, product_data
from inventory.models import InventoryMovement
from sales.services import create_draft_sale, finalize_sale
from sales.tests.factories import line, make_product, make_user


class ProductCreateApiTests(APITestCase):
    def setUp(self):
        self.manager = grant(make_user(username="manager"), COST, STOCK)
        self.cashier = make_user(username="cashier")
        self.url = reverse("product-list")

    def test_create_with_initial_stock(self):
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.url, product_data(initial_stock=89), format="json"
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["stock_quantity"], 89)
        self.assertEqual(response.data["model"], "BG66 Ultimax")
        self.assertEqual(response.data["supplier"], "Yonex Philippines")
        product = Product.objects.get(pk=response.data["id"])
        self.assertEqual(product.events.get().action, ProductEvent.Action.CREATED)
        self.assertEqual(
            InventoryMovement.objects.get(product=product).quantity_change, 89
        )

    def test_negative_initial_stock_is_a_field_error(self):
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.url, product_data(initial_stock=-1), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("initial_stock", response.data)

    def test_duplicate_sku_is_a_field_error(self):
        self.client.force_authenticate(self.manager)
        make_product(sku="YNX-BG66-UM")

        response = self.client.post(
            self.url, product_data(sku="ynx-bg66-um"), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("sku", response.data)

    def test_cost_requires_permission(self):
        self.client.force_authenticate(self.cashier)

        forbidden = self.client.post(self.url, product_data(), format="json")
        data = product_data()
        data.pop("cost_price")
        created = self.client.post(self.url, data | {"sku": "OTHER"}, format="json")

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(created.status_code, 201, created.data)
        self.assertNotIn("cost_price", created.data)
        self.assertEqual(Product.objects.get(sku="OTHER").cost_price, Decimal("0.00"))


class ProductEditApiTests(APITestCase):
    def setUp(self):
        self.manager = grant(make_user(username="manager"), COST, STOCK)
        self.cashier = make_user(username="cashier", first_name="Cash", last_name="Ier")
        self.product = make_product(
            selling_price=Decimal("450.00"),
            cost_price=Decimal("320.00"),
            stock_quantity=89,
        )
        self.url = reverse("product-detail", kwargs={"pk": self.product.pk})

    def patch(self, user, body):
        self.client.force_authenticate(user)
        return self.client.patch(self.url, body, format="json")

    def test_successful_edit_returns_detail_with_last_event(self):
        response = self.patch(
            self.manager,
            {
                "changes": {"selling_price": "480.00", "stock_quantity": 85},
                "expected": {"selling_price": "450.00", "stock_quantity": 89},
                "reason": "Supplier price increase; recount",
            },
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["selling_price"], "480.00")
        self.assertEqual(response.data["stock_quantity"], 85)
        self.assertEqual(response.data["last_event"]["action"], "UPDATED")
        self.assertEqual(
            response.data["last_event"]["performed_by"]["username"], "manager"
        )

    def test_validation_errors(self):
        cases = [
            (
                {
                    "changes": {"name": "X"},
                    "expected": {"name": self.product.name},
                    "reason": "",
                },
                "reason",
            ),
            ({"changes": {}, "expected": {}, "reason": "x"}, "changes"),
            ({"changes": {"name": "X"}, "expected": {}, "reason": "x"}, "expected"),
            (
                {
                    "changes": {"selling_price": "-1"},
                    "expected": {"selling_price": "450.00"},
                    "reason": "x",
                },
                "selling_price",
            ),
            (
                {
                    "changes": {"stock_quantity": -1},
                    "expected": {"stock_quantity": 89},
                    "reason": "x",
                },
                "stock_quantity",
            ),
            (
                {"changes": {"unknown": 1}, "expected": {"unknown": 0}, "reason": "x"},
                "changes",
            ),
        ]
        for body, key in cases:
            with self.subTest(key=key, body=body):
                response = self.patch(self.manager, body)
                self.assertEqual(response.status_code, 400)
                self.assertIn(key, str(response.data))

    def test_permission_errors(self):
        for changes, expected in [
            ({"stock_quantity": 85}, {"stock_quantity": 89}),
            ({"cost_price": "300.00"}, {"cost_price": "320.00"}),
        ]:
            with self.subTest(changes=changes):
                response = self.patch(
                    self.cashier,
                    {"changes": changes, "expected": expected, "reason": "x"},
                )
                self.assertEqual(response.status_code, 403)

    def test_conflict_returns_current_values(self):
        Product.objects.filter(pk=self.product.pk).update(
            selling_price=Decimal("470.00")
        )

        response = self.patch(
            self.manager,
            {
                "changes": {"selling_price": "480.00"},
                "expected": {"selling_price": "450.00"},
                "reason": "x",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["current"], {"selling_price": "470.00"})
        self.assertIn("changed by someone else", response.data["detail"])

    def test_put_is_not_allowed(self):
        self.client.force_authenticate(self.manager)

        response = self.client.put(self.url, {}, format="json")

        self.assertEqual(response.status_code, 405)

    def test_anonymous_requests_are_rejected(self):
        self.client.force_authenticate(None)
        requests = [
            ("get", self.url),
            ("patch", self.url),
            ("get", reverse("product-history", kwargs={"pk": self.product.pk})),
            ("post", reverse("product-list")),
            ("post", reverse("product-deactivate", kwargs={"pk": self.product.pk})),
            ("post", reverse("product-reactivate", kwargs={"pk": self.product.pk})),
        ]
        for method, url in requests:
            with self.subTest(method=method, url=url):
                self.assertEqual(
                    getattr(self.client, method)(url, {}, format="json").status_code,
                    401,
                )

    def test_detail_is_two_queries(self):
        update_product(
            product_id=self.product.pk,
            user=self.manager,
            changes={"name": "Renamed"},
            expected={"name": self.product.name},
            reason="Typo",
        )
        self.client.force_authenticate(self.manager)
        self.manager.has_perm("catalog.view_product_cost")

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(
            response.data["last_event"]["performed_by"]["display_name"], "manager"
        )

    def test_detail_without_history_has_null_last_event(self):
        self.client.force_authenticate(self.manager)

        self.assertIsNone(self.client.get(self.url).data["last_event"])


class ProductHistoryApiTests(APITestCase):
    def setUp(self):
        self.manager = grant(
            make_user(username="manager", first_name="Maria", last_name="Reyes"),
            COST,
            STOCK,
        )
        self.cashier = make_user(username="cashier")
        self.product = make_product(
            selling_price=Decimal("450.00"), cost_price=Decimal("320.00")
        )
        for changes, expected, reason in [
            ({"cost_price": Decimal("300.00")}, {"cost_price": "320.00"}, "Cost down"),
            (
                {"selling_price": Decimal("480.00")},
                {"selling_price": "450.00"},
                "Price up",
            ),
        ]:
            update_product(
                product_id=self.product.pk,
                user=self.manager,
                changes=changes,
                expected=expected,
                reason=reason,
            )
        self.url = reverse("product-history", kwargs={"pk": self.product.pk})

    def test_history_is_paginated_newest_first(self):
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        first = response.data["results"][0]
        self.assertEqual(first["reason"], "Price up")
        self.assertEqual(
            first["performed_by"],
            {
                "id": self.manager.pk,
                "username": "manager",
                "display_name": "Maria Reyes",
            },
        )
        self.assertEqual(
            response.data["results"][1]["changes"], {"cost_price": ["320.00", "300.00"]}
        )

    def test_history_hides_cost_changes_without_permission(self):
        self.client.force_authenticate(self.cashier)

        response = self.client.get(self.url)

        self.assertEqual(response.data["results"][1]["changes"], {})

    def test_history_is_three_queries(self):
        self.client.force_authenticate(self.manager)
        self.manager.has_perm("catalog.view_product_cost")

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.url)

        # Product existence (404 check), count, page with performed_by joined.
        self.assertEqual(len(ctx.captured_queries), 3)


class ProductActivationApiTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock_quantity=4)
        self.client.force_authenticate(self.user)

    def test_blank_reason_is_rejected(self):
        for name in ("product-deactivate", "product-reactivate"):
            with self.subTest(name=name):
                response = self.client.post(
                    reverse(name, kwargs={"pk": self.product.pk}),
                    {"reason": "  "},
                    format="json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("reason", response.data)

    def test_deactivation_keeps_past_sales_intact(self):
        sale = create_draft_sale(user=self.user, items=[line(self.product, 1)])
        finalize_sale(sale_id=sale.pk, user=self.user)

        response = self.client.post(
            reverse("product-deactivate", kwargs={"pk": self.product.pk}),
            {"reason": "Discontinued"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["product"]["is_active"])
        sale.refresh_from_db()
        item = sale.items.get()
        self.assertEqual(item.product_id, self.product.pk)
        self.assertEqual(item.quantity, 1)
        self.assertEqual(
            self.product.events.get().action, ProductEvent.Action.DEACTIVATED
        )

    def test_non_text_reason_is_a_validation_error(self):
        for reason in (["a"], {"x": 1}, None):
            with self.subTest(reason=reason):
                response = self.client.post(
                    reverse("product-deactivate", kwargs={"pk": self.product.pk}),
                    {"reason": reason},
                    format="json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("reason", response.data)
