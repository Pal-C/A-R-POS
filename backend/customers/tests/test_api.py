from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from customers.tests.factories import make_customer, make_user


class CustomerAPITestCase(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.list_url = reverse("customer-list-create")

    def detail_url(self, pk):
        return reverse("customer-detail", kwargs={"pk": pk})

    def count_queries(self, method, url, data=None):
        with CaptureQueriesContext(connection) as ctx:
            response = getattr(self.client, method)(url, data, format="json")
        self.assertLess(response.status_code, 300, getattr(response, "data", None))
        return len(ctx.captured_queries)


# ---------------------------------------------------------------------------
# US1: find a customer
# ---------------------------------------------------------------------------


class CustomerListAPITests(CustomerAPITestCase):
    def test_list_item_shape_and_pagination(self):
        for i in range(21):
            make_customer(full_name=f"Customer {i:02d}", phone_number="0917")

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 21)
        self.assertIsNotNone(response.data["next"])
        self.assertEqual(len(response.data["results"]), 20)
        self.assertEqual(
            set(response.data["results"][0]),
            {"id", "full_name", "phone_number", "email", "is_active"},
        )

    def test_search_and_status(self):
        make_customer(full_name="Ana Reyes", phone_number="0917 123 4567")
        make_customer(full_name="Old Ana", is_active=False)

        def names(**params):
            response = self.client.get(self.list_url, params)
            self.assertEqual(response.status_code, 200)
            return [row["full_name"] for row in response.data["results"]]

        self.assertEqual(names(search="ana"), ["Ana Reyes"])
        self.assertEqual(names(search="09171234567"), ["Ana Reyes"])
        self.assertEqual(names(search="ana", status="archived"), ["Old Ana"])
        self.assertEqual(names(search="", status="all"), ["Ana Reyes", "Old Ana"])
        self.assertEqual(names(search="nobody"), [])

    def test_invalid_status_returns_400(self):
        response = self.client.get(self.list_url, {"status": "deleted"})
        self.assertEqual(response.status_code, 400)

    def test_list_query_count_is_constant(self):
        make_customer()
        one = self.count_queries("get", self.list_url)
        for _ in range(24):
            make_customer()
        self.assertEqual(self.count_queries("get", self.list_url), one)

    def test_unauthenticated_is_rejected(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(self.list_url).status_code, (401, 403))


class CustomerDetailAPITests(CustomerAPITestCase):
    def test_detail_shows_all_fields(self):
        customer = make_customer(
            full_name="Ana Reyes",
            phone_number="0917 123 4567",
            email="ana@example.com",
            address="Quezon City",
            notes="Prefers 26 lbs",
        )

        response = self.client.get(self.detail_url(customer.pk))

        self.assertEqual(response.status_code, 200)
        data = response.data
        for field in ("full_name", "phone_number", "email", "address", "notes"):
            self.assertEqual(data[field], getattr(customer, field))
        self.assertTrue(data["is_active"])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
        self.assertNotIn("phone_normalized", data)

    def test_unknown_customer_returns_404(self):
        self.assertEqual(self.client.get(self.detail_url(999999)).status_code, 404)

    def test_unauthenticated_is_rejected(self):
        customer = make_customer()
        self.client.force_authenticate(None)
        response = self.client.get(self.detail_url(customer.pk))
        self.assertIn(response.status_code, (401, 403))


# ---------------------------------------------------------------------------
# US2: register a customer
# ---------------------------------------------------------------------------


class CustomerCreateAPITests(CustomerAPITestCase):
    def test_create_returns_detail_and_empty_duplicates(self):
        response = self.client.post(
            self.list_url,
            {"full_name": "Ana Reyes", "phone_number": "0917 123 4567"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["full_name"], "Ana Reyes")
        self.assertTrue(response.data["is_active"])
        self.assertIn("created_at", response.data)
        self.assertEqual(response.data["duplicate_phone_customers"], [])

    def test_duplicate_phone_warns_but_saves(self):
        existing = make_customer(full_name="Ana", phone_number="0917 123 4567")

        response = self.client.post(
            self.list_url,
            {"full_name": "Ana's son", "phone_number": "+63 917-123-4567"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            [c["id"] for c in response.data["duplicate_phone_customers"]],
            [existing.pk],
        )

    def test_validation_errors_are_field_keyed(self):
        cases = {
            "full_name": {"full_name": "   "},
            "email": {"full_name": "Ana", "email": "nope"},
            "phone_number": {"full_name": "Ana", "phone_number": "0917-abc"},
        }
        for field, payload in cases.items():
            with self.subTest(field):
                response = self.client.post(self.list_url, payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

    def test_read_only_fields_are_ignored(self):
        response = self.client.post(
            self.list_url,
            {
                "full_name": "Ana",
                "phone_number": "0917",
                "is_active": False,
                "created_at": "2020-01-01T00:00:00Z",
                "phone_normalized": "999",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_active"])
        self.assertFalse(response.data["created_at"].startswith("2020"))
        from customers.models import Customer

        self.assertEqual(
            Customer.objects.get(pk=response.data["id"]).phone_normalized, "0917"
        )


class PhoneMatchesAPITests(CustomerAPITestCase):
    def test_returns_unpaginated_list(self):
        ana = make_customer(full_name="Ana", phone_number="0917 123 4567")
        url = reverse("customer-phone-matches")

        response = self.client.get(url, {"phone": "+63 917 123 4567"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c["id"] for c in response.data], [ana.pk])
        self.assertEqual(
            set(response.data[0]),
            {"id", "full_name", "phone_number", "email", "is_active"},
        )

        response = self.client.get(url, {"phone": "", "exclude_id": ana.pk})
        self.assertEqual(response.data, [])

    def test_unauthenticated_is_rejected(self):
        self.client.force_authenticate(None)
        response = self.client.get(reverse("customer-phone-matches"), {"phone": "1"})
        self.assertIn(response.status_code, (401, 403))


# ---------------------------------------------------------------------------
# US3: update customer information
# ---------------------------------------------------------------------------


class CustomerUpdateAPITests(CustomerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_customer(full_name="Ana Reyes", phone_number="0917 123 4567")

    def test_patch_updates_and_lists_other_duplicates(self):
        sibling = make_customer(full_name="Ben", phone_number="0918 000 1111")

        response = self.client.patch(
            self.detail_url(self.customer.pk),
            {"phone_number": "+63 918 000 1111"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["phone_number"], "+63 918 000 1111")
        self.assertEqual(
            [c["id"] for c in response.data["duplicate_phone_customers"]], [sibling.pk]
        )
        search = self.client.get(self.list_url, {"search": "09180001111"}).data
        self.assertIn(self.customer.pk, [c["id"] for c in search["results"]])

    def test_patch_validation_and_404(self):
        response = self.client.patch(
            self.detail_url(self.customer.pk), {"full_name": ""}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("full_name", response.data)

        response = self.client.patch(
            self.detail_url(self.customer.pk), {"email": "bad"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

        response = self.client.patch(self.detail_url(999999), {"notes": "x"}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_patch_ignores_read_only_fields(self):
        response = self.client.patch(
            self.detail_url(self.customer.pk),
            {"notes": "VIP", "is_active": False, "created_at": "2020-01-01T00:00:00Z"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_active"])
        self.assertEqual(response.data["notes"], "VIP")

    def test_corrected_name_shows_on_past_sales(self):
        from customers.tests.factories import make_finalized_sale

        sale = make_finalized_sale(self.customer, self.user)
        self.client.patch(
            self.detail_url(self.customer.pk), {"full_name": "Ana R. Cruz"}, format="json"
        )

        response = self.client.get(reverse("sale-detail", kwargs={"pk": sale.pk}))
        self.assertEqual(response.data["customer_name"], "Ana R. Cruz")


# ---------------------------------------------------------------------------
# US4: customer history
# ---------------------------------------------------------------------------


class CustomerHistoryAPITests(CustomerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_customer(full_name="Ana Reyes")

    def history_url(self, name, pk=None):
        return reverse(f"customer-{name}", kwargs={"pk": pk or self.customer.pk})

    def make_history(self, n=1):
        from customers.tests.factories import (
            make_finalized_sale,
            make_preorder,
            make_stringing_order,
        )

        for _ in range(n):
            make_finalized_sale(self.customer, self.user, paid="100.00")
            make_stringing_order(self.customer, self.user)
            make_preorder(self.customer, self.user)

    def test_detail_includes_summary(self):
        self.make_history()
        summary = self.client.get(self.detail_url(self.customer.pk)).data["summary"]

        self.assertEqual(
            set(summary),
            {
                "sales_count",
                "stringing_orders_count",
                "preorders_count",
                "total_spent",
                "outstanding_balance",
                "open_preorders_count",
                "unfinished_stringing_orders_count",
            },
        )
        self.assertEqual(summary["sales_count"], 1)
        self.assertEqual(summary["total_spent"], "100.00")
        # sale 1500 - 100 + stringing 450 + pre-order 5000
        self.assertEqual(summary["outstanding_balance"], "6850.00")

    def test_sales_history_rows(self):
        from customers.tests.factories import make_finalized_sale
        from sales.services import cancel_sale, create_draft_sale
        from sales.tests.factories import line, make_product

        older = make_finalized_sale(self.customer, self.user, paid="100.00")
        newer = make_finalized_sale(self.customer, self.user)
        cancel_sale(sale_id=newer.pk, user=self.user, reason="test")
        create_draft_sale(
            user=self.user, customer=self.customer, items=[line(make_product(), 1)]
        )

        response = self.client.get(self.history_url("sales"))

        self.assertEqual(response.status_code, 200)
        rows = response.data["results"]
        self.assertEqual([r["id"] for r in rows], [newer.pk, older.pk])  # no draft
        self.assertEqual(
            set(rows[0]),
            {"id", "sale_number", "finalized_at", "status", "total_amount",
             "amount_paid", "balance"},
        )
        self.assertEqual(rows[0]["balance"], "0.00")  # cancelled
        self.assertEqual(rows[1]["amount_paid"], "100.00")
        self.assertEqual(rows[1]["balance"], "1400.00")

    def test_stringing_and_preorder_rows(self):
        self.make_history()

        rows = self.client.get(self.history_url("stringing-orders")).data["results"]
        self.assertEqual(
            set(rows[0]),
            {"id", "order_number", "racket_description", "string_type", "tension",
             "status", "total_amount", "created_at", "completed_at"},
        )
        self.assertEqual(rows[0]["total_amount"], "450.00")

        rows = self.client.get(self.history_url("preorders")).data["results"]
        self.assertEqual(
            set(rows[0]),
            {"id", "order_number", "product", "product_name", "product_sku",
             "quantity", "total_amount", "expected_arrival_date", "status",
             "amount_paid", "created_at"},
        )
        self.assertEqual(rows[0]["total_amount"], "5000.00")
        self.assertEqual(rows[0]["amount_paid"], "0.00")

    def test_history_is_paginated_newest_first(self):
        from customers.tests.factories import make_stringing_order

        orders = [make_stringing_order(self.customer, self.user) for _ in range(21)]
        response = self.client.get(self.history_url("stringing-orders"))
        self.assertEqual(response.data["count"], 21)
        self.assertEqual(response.data["results"][0]["id"], orders[-1].pk)
        self.assertIsNotNone(response.data["next"])

    def test_empty_history_and_unknown_customer(self):
        for name in ("sales", "stringing-orders", "preorders"):
            with self.subTest(name):
                response = self.client.get(self.history_url(name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["results"], [])
                response = self.client.get(self.history_url(name, pk=999999))
                self.assertEqual(response.status_code, 404)

    def test_query_counts_are_constant(self):
        self.make_history(1)
        detail_one = self.count_queries("get", self.detail_url(self.customer.pk))
        lists_one = {
            n: self.count_queries("get", self.history_url(n))
            for n in ("sales", "stringing-orders", "preorders")
        }

        self.make_history(10)
        self.assertEqual(
            self.count_queries("get", self.detail_url(self.customer.pk)), detail_one
        )
        for name, count in lists_one.items():
            with self.subTest(name):
                self.assertEqual(self.count_queries("get", self.history_url(name)), count)


# ---------------------------------------------------------------------------
# US5: archive, reactivate, delete
# ---------------------------------------------------------------------------


class CustomerArchiveDeleteAPITests(CustomerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_customer(full_name="Ana Reyes")
        self.archiver = make_user(permissions=["archive_customer"])
        self.deleter = make_user(permissions=["delete_customer"])

    def action(self, name, pk=None):
        return reverse(f"customer-{name}", kwargs={"pk": pk or self.customer.pk})

    def test_archive_and_reactivate(self):
        self.client.force_authenticate(self.archiver)

        response = self.client.post(self.action("archive"))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["is_active"])
        event = response.data["last_archive_event"]
        self.assertEqual(event["action"], "ARCHIVED")
        self.assertEqual(event["performed_by"], self.archiver.pk)
        self.assertEqual(event["performed_by_name"], self.archiver.username)

        self.assertEqual(self.client.post(self.action("archive")).status_code, 400)

        listed = self.client.get(self.list_url).data["results"]
        self.assertNotIn(self.customer.pk, [c["id"] for c in listed])
        archived = self.client.get(self.list_url, {"status": "archived"}).data["results"]
        self.assertIn(self.customer.pk, [c["id"] for c in archived])

        response = self.client.post(self.action("reactivate"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_active"])
        self.assertEqual(response.data["last_archive_event"]["action"], "REACTIVATED")
        self.assertEqual(self.client.post(self.action("reactivate")).status_code, 400)

    def test_detail_without_events_has_null_last_archive_event(self):
        response = self.client.get(self.detail_url(self.customer.pk))
        self.assertIsNone(response.data["last_archive_event"])

    def test_archived_customer_cannot_be_used_on_new_sale(self):
        from sales.tests.factories import make_product

        self.client.force_authenticate(self.archiver)
        self.client.post(self.action("archive"))

        response = self.client.post(
            reverse("sale-list-create"),
            {
                "customer_id": self.customer.pk,
                "items": [{"product_id": make_product().pk, "quantity": 1}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_permissions(self):
        for user in (self.user, self.deleter):
            with self.subTest(user=user.username):
                self.client.force_authenticate(user)
                self.assertEqual(self.client.post(self.action("archive")).status_code, 403)
                self.assertEqual(
                    self.client.post(self.action("reactivate")).status_code, 403
                )

        for user in (self.user, self.archiver):
            with self.subTest(user=user.username):
                self.client.force_authenticate(user)
                response = self.client.delete(self.detail_url(self.customer.pk))
                self.assertEqual(response.status_code, 403)

        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

    def test_delete(self):
        from customers.models import Customer
        from customers.tests.factories import make_finalized_sale

        self.client.force_authenticate(self.deleter)

        with_history = make_customer()
        make_finalized_sale(with_history, self.user)
        response = self.client.delete(self.detail_url(with_history.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Archive", str(response.data))

        response = self.client.delete(self.detail_url(self.customer.pk))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Customer.objects.filter(pk=self.customer.pk).exists())

        self.assertEqual(self.client.delete(self.detail_url(999999)).status_code, 404)
        self.client.force_authenticate(self.archiver)
        self.assertEqual(self.client.post(self.action("archive", 999999)).status_code, 404)
