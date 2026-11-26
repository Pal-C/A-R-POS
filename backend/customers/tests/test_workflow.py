"""
Story-level run through the customer API (quickstart.md):
create → find → edit → transact → history → archive → reactivate → delete.
"""

from django.urls import reverse
from rest_framework.test import APITestCase

from customers.models import CustomerAuditEvent
from customers.tests.factories import make_user
from sales.tests.factories import make_product


class CustomerWorkflowTests(APITestCase):
    def setUp(self):
        self.cashier = make_user(username="cashier")
        self.manager = make_user(
            username="manager", permissions=["archive_customer", "delete_customer"]
        )
        self.client.force_authenticate(self.cashier)
        self.racket = make_product(name="Racket")  # 1500

    def call(self, method, url, data=None, expected=200):
        response = getattr(self.client, method)(url, data, format="json")
        self.assertEqual(response.status_code, expected, getattr(response, "data", None))
        return response.data

    def test_customer_lifecycle(self):
        customers_url = reverse("customer-list-create")

        # Register (US2), with a household member sharing the phone.
        ana = self.call(
            "post",
            customers_url,
            {"full_name": "Ana Reyes", "phone_number": "0917 123 4567"},
            201,
        )
        son = self.call(
            "post",
            customers_url,
            {"full_name": "Paolo Reyes", "phone_number": "+63 917-123-4567"},
            201,
        )
        self.assertEqual([c["id"] for c in son["duplicate_phone_customers"]], [ana["id"]])

        # Find (US1) by name and by phone in several formats.
        for search in ("ana", "4567", "09171234567", "+63 917"):
            with self.subTest(search=search):
                results = self.call("get", customers_url, {"search": search})["results"]
                self.assertIn(ana["id"], [c["id"] for c in results])

        # Edit (US3).
        detail_url = reverse("customer-detail", kwargs={"pk": ana["id"]})
        ana = self.call("patch", detail_url, {"email": "ana@example.com"})
        self.assertEqual(ana["email"], "ana@example.com")

        # Transact: a sale paid in part.
        sale = self.call(
            "post",
            reverse("sale-list-create"),
            {
                "customer_id": ana["id"],
                "items": [{"product_id": self.racket.pk, "quantity": 2}],
            },
            201,
        )
        self.call("post", reverse("sale-finalize", kwargs={"pk": sale["id"]}))
        self.call(
            "post",
            reverse("payment-list-create"),
            {"sale": sale["id"], "amount": "1000.00", "payment_method": "CASH"},
            201,
        )

        # History (US4).
        summary = self.call("get", detail_url)["summary"]
        self.assertEqual(summary["sales_count"], 1)
        self.assertEqual(summary["total_spent"], "1000.00")
        self.assertEqual(summary["outstanding_balance"], "2000.00")
        rows = self.call("get", reverse("customer-sales", kwargs={"pk": ana["id"]}))[
            "results"
        ]
        self.assertEqual(rows[0]["balance"], "2000.00")

        # Archive (US5): hidden by default and unusable on new sales.
        self.client.force_authenticate(self.manager)
        archived = self.call("post", reverse("customer-archive", kwargs={"pk": ana["id"]}))
        self.assertFalse(archived["is_active"])
        self.assertEqual(archived["last_archive_event"]["performed_by_name"], "manager")

        results = self.call("get", customers_url, {"search": "ana"})["results"]
        self.assertNotIn(ana["id"], [c["id"] for c in results])
        self.call(
            "post",
            reverse("sale-list-create"),
            {
                "customer_id": ana["id"],
                "items": [{"product_id": self.racket.pk, "quantity": 1}],
            },
            400,
        )
        # Past sale still shows her.
        old_sale = self.call("get", reverse("sale-detail", kwargs={"pk": sale["id"]}))
        self.assertEqual(old_sale["customer_name"], "Ana Reyes")

        # Reactivate.
        self.call("post", reverse("customer-reactivate", kwargs={"pk": ana["id"]}))
        results = self.call("get", customers_url, {"search": "ana"})["results"]
        self.assertIn(ana["id"], [c["id"] for c in results])

        # Delete refused for Ana (history), allowed for her son (none).
        self.call("delete", detail_url, expected=400)
        son_url = reverse("customer-detail", kwargs={"pk": son["id"]})
        self.call("delete", son_url, expected=204)
        self.call("get", son_url, expected=404)

        self.assertEqual(
            list(
                CustomerAuditEvent.objects.order_by("id").values_list(
                    "action", "customer_name", "performed_by__username"
                )
            ),
            [
                ("ARCHIVED", "Ana Reyes", "manager"),
                ("REACTIVATED", "Ana Reyes", "manager"),
                ("DELETED", "Paolo Reyes", "manager"),
            ],
        )
