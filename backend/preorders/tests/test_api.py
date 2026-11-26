"""API tests for /api/preorders/ (contracts/preorders-api.md)."""

from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from preorders.models import PreOrder
from preorders.selectors import store_today
from preorders.services import cancel_preorder, change_status
from preorders.tests.factories import (
    ALL_PERMISSIONS,
    make_customer,
    make_payment,
    make_preorder,
    make_product,
    make_user,
)

S = PreOrder.Status
LIST_URL = reverse("preorder-list-create")


def url(name, pk):
    return reverse(name, kwargs={"pk": getattr(pk, "pk", pk)})


def product_url(name, product):
    return reverse(name, kwargs={"product_id": getattr(product, "pk", product)})


def move(preorder, *statuses):
    for status in statuses:
        change_status(
            preorder_id=preorder.pk, user=preorder.created_by, to_status=status
        )
    preorder.refresh_from_db()
    return preorder


class PreOrderAPITestCase(APITestCase):
    def setUp(self):
        self.manager = make_user(perms=ALL_PERMISSIONS)
        self.staff = make_user()
        self.customer = make_customer(full_name="Ana Reyes", phone_number="09171234567")
        self.product = make_product(name="Astrox 100ZZ", sku="RKT-AX100")
        self.client.force_authenticate(self.manager)

    def as_user(self, user):
        self.client.force_authenticate(user)


class CreateDetailEditAPITests(PreOrderAPITestCase):
    def payload(self, **overrides):
        data = {
            "customer": self.customer.pk,
            "product": self.product.pk,
            "quantity": 2,
            "agreed_unit_price": "5000.00",
            "expected_arrival_date": (store_today() + timedelta(days=21)).isoformat(),
        }
        data.update(overrides)
        return data

    def test_create(self):
        response = self.client.post(LIST_URL, self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        self.assertRegex(data["order_number"], r"^PO-\d{4}-\d{6}$")
        self.assertEqual(data["status"], S.PENDING)
        self.assertEqual(data["status_display"], "Pending")
        self.assertEqual(data["total_amount"], "10000.00")
        self.assertEqual(data["balance"], "10000.00")
        self.assertEqual(data["payment_state"], "UNPAID")
        self.assertFalse(data["is_overdue"])
        self.assertEqual(data["customer"]["full_name"], "Ana Reyes")
        self.assertEqual(data["product"]["sku"], "RKT-AX100")
        self.assertEqual(data["notes"], "")

    def test_price_defaults_to_selling_price(self):
        payload = self.payload()
        del payload["agreed_unit_price"]
        response = self.client.post(LIST_URL, payload, format="json")
        self.assertEqual(response.data["agreed_unit_price"], "5000.00")

    def test_create_errors(self):
        cases = {
            "quantity": {"quantity": 0},
            "agreed_unit_price": {"agreed_unit_price": "-1"},
            "expected_arrival_date": {
                "expected_arrival_date": (store_today() - timedelta(days=1)).isoformat()
            },
            "customer": {"customer": make_customer(is_active=False).pk},
            "product": {"product": make_product(is_active=False).pk},
        }
        for field, override in cases.items():
            with self.subTest(field=field):
                response = self.client.post(
                    LIST_URL, self.payload(**override), format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        response = self.client.post(LIST_URL, {}, format="json")
        for field in ("customer", "product", "quantity"):
            self.assertIn(field, response.data)
        self.assertEqual(PreOrder.objects.count(), 0)

    def test_detail_404_and_no_delete(self):
        preorder = make_preorder(self.manager)
        self.assertEqual(
            self.client.get(url("preorder-detail", 999999)).status_code, 404
        )
        self.assertEqual(
            self.client.delete(url("preorder-detail", preorder)).status_code, 405
        )

    def test_patch(self):
        preorder = make_preorder(self.manager)
        response = self.client.patch(
            url("preorder-detail", preorder),
            {"quantity": 3, "notes": "Black"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total_amount"], "15000.00")
        self.assertEqual(response.data["notes"], "Black")

    def test_patch_rules(self):
        preorder = make_preorder(self.manager)
        make_payment(preorder, "8000.00")
        response = self.client.patch(
            url("preorder-detail", preorder), {"quantity": 1}, format="json"
        )
        self.assertEqual(response.status_code, 400)

        self.as_user(self.staff)
        response = self.client.patch(
            url("preorder-detail", preorder),
            {"agreed_unit_price": "4500.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        self.as_user(self.manager)
        response = self.client.patch(
            url("preorder-detail", preorder),
            {"agreed_unit_price": "4500.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.patch(
                url("preorder-detail", 999999), {}, format="json"
            ).status_code,
            404,
        )

    def test_detail_query_count(self):
        preorder = make_preorder(self.manager)
        make_payment(preorder, "100.00")
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(
                self.client.get(url("preorder-detail", preorder)).status_code, 200
            )
        self.assertEqual(len(ctx.captured_queries), 1)


class PaymentAPITests(PreOrderAPITestCase):
    def setUp(self):
        super().setUp()
        self.preorder = make_preorder(self.manager)  # 10000
        self.url = url("preorder-payments", self.preorder)

    def post(self, data):
        return self.client.post(self.url, data, format="json")

    def test_deposit_then_full(self):
        response = self.post({"amount": "4000.00", "payment_method": "CASH"})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["payment"]["amount"], "4000.00")
        self.assertEqual(response.data["preorder"]["balance"], "6000.00")
        self.assertEqual(response.data["preorder"]["payment_state"], "PARTIAL")
        response = self.post({"amount": "6000.00", "payment_method": "GCASH"})
        self.assertEqual(response.data["preorder"]["payment_state"], "PAID")

    def test_errors(self):
        self.post({"amount": "4000.00", "payment_method": "CASH"})
        for data in (
            {"amount": "7000.00", "payment_method": "CASH"},
            {"amount": "0", "payment_method": "CASH"},
            {"amount": "10.00"},
            {"amount": "10.00", "payment_method": "CASH", "payment_type": "REFUND"},
        ):
            with self.subTest(data=data):
                self.assertEqual(self.post(data).status_code, 400)

    def test_permissions(self):
        make_payment(self.preorder, "100.00")
        self.as_user(self.staff)
        self.assertEqual(
            self.post({"amount": "10", "payment_method": "CASH"}).status_code, 403
        )
        self.as_user(make_user(perms=["sales.record_payment"]))
        response = self.post(
            {
                "amount": "10",
                "payment_method": "CASH",
                "payment_type": "REFUND",
                "reason": "r",
            }
        )
        self.assertEqual(response.status_code, 403)

    def test_cancelled_shows_refund_due(self):
        make_payment(self.preorder, "4000.00")
        cancel_preorder(preorder_id=self.preorder.pk, user=self.manager, reason="x")
        detail = self.client.get(url("preorder-detail", self.preorder)).data
        self.assertEqual(detail["refund_due"], "4000.00")
        self.assertEqual(detail["balance"], "0.00")
        self.assertEqual(
            self.post({"amount": "1", "payment_method": "CASH"}).status_code, 400
        )
        response = self.post(
            {
                "amount": "4000.00",
                "payment_method": "CASH",
                "payment_type": "REFUND",
                "reason": "Cancelled",
            }
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["preorder"]["refund_due"], "0.00")

    def test_list_and_404(self):
        make_payment(self.preorder, "100.00")
        make_payment(self.preorder, "50.00")
        response = self.client.get(self.url)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            self.client.get(url("preorder-payments", 999999)).status_code, 404
        )


class StatusArrivalFulfillAPITests(PreOrderAPITestCase):
    def test_status_change(self):
        preorder = make_preorder(self.manager)
        response = self.client.post(
            url("preorder-status", preorder), {"status": "ORDERED"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status_display"], "Ordered from Supplier")
        self.assertIsNotNone(response.data["ordered_at"])

        for data in (
            {"status": "FULFILLED"},
            {"status": "PENDING", "expected_status": "PENDING"},
        ):
            with self.subTest(data=data):
                response = self.client.post(
                    url("preorder-status", preorder), data, format="json"
                )
                self.assertEqual(response.status_code, 400)
        response = self.client.post(
            url("preorder-status", preorder),
            {"status": "ARRIVED", "expected_status": "PENDING"},
            format="json",
        )
        self.assertEqual(response.data["current_status"], S.ORDERED)

    def test_summary_and_arrivals(self):
        older = move(
            make_preorder(self.manager, product=self.product, quantity=2), S.ORDERED
        )
        newer = move(
            make_preorder(self.manager, product=self.product, quantity=1), S.ORDERED
        )

        summary = self.client.get(product_url("preorder-product-summary", self.product))
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.data["waiting"]["ORDERED"], {"orders": 2, "units": 3})
        self.assertEqual(
            [o["id"] for o in summary.data["ordered_preorders"]], [older.pk, newer.pk]
        )

        arrivals = product_url("preorder-product-arrivals", self.product)
        response = self.client.post(arrivals, {"received_quantity": 2}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([o["id"] for o in response.data["marked"]], [older.pk])
        self.assertEqual(response.data["units_left"], 0)

        response = self.client.post(
            arrivals,
            {"received_quantity": 1, "preorder_ids": [newer.pk]},
            format="json",
        )
        self.assertEqual([o["id"] for o in response.data["marked"]], [newer.pk])

        response = self.client.post(arrivals, {"received_quantity": 4}, format="json")
        self.assertEqual(
            response.data, {"marked": [], "units_used": 0, "units_left": 4}
        )

    def test_arrival_errors(self):
        arrivals = product_url("preorder-product-arrivals", self.product)
        for data in (
            {"received_quantity": 0},
            {},
            {"received_quantity": 1, "preorder_ids": []},
            {"received_quantity": 1, "preorder_ids": [999999]},
        ):
            with self.subTest(data=data):
                self.assertEqual(
                    self.client.post(arrivals, data, format="json").status_code, 400
                )
        missing = product_url("preorder-product-arrivals", 999999)
        self.assertEqual(
            self.client.post(
                missing, {"received_quantity": 1}, format="json"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                product_url("preorder-product-summary", 999999)
            ).status_code,
            404,
        )

    def test_fulfill(self):
        preorder = make_preorder(self.manager)
        fulfill = url("preorder-fulfill", preorder)
        self.assertEqual(self.client.post(fulfill).status_code, 400)  # not arrived
        move(preorder, S.ORDERED, S.ARRIVED)
        response = self.client.post(fulfill)
        self.assertEqual(response.status_code, 400)
        self.assertIn("10000.00", str(response.data))
        make_payment(preorder, "10000.00")
        response = self.client.post(fulfill)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], S.FULFILLED)
        self.assertEqual(response.data["fulfilled_by"]["id"], self.manager.pk)
        self.assertEqual(
            self.client.post(url("preorder-fulfill", 999999)).status_code, 404
        )


class LegacyFulfilledAPITests(PreOrderAPITestCase):
    def test_unpaid_legacy_fulfilled_shows_real_balance(self):
        preorder = make_preorder(self.manager)
        make_payment(preorder, "4000.00")
        PreOrder.objects.filter(pk=preorder.pk).update(
            status=S.FULFILLED,
            fulfilled_at=preorder.created_at,
            fulfilled_by=self.manager,
        )
        detail = self.client.get(url("preorder-detail", preorder)).data
        self.assertEqual(detail["balance"], "6000.00")
        self.assertEqual(detail["payment_state"], "PARTIAL")
        response = self.client.post(
            url("preorder-payments", preorder),
            {"amount": "6000.00", "payment_method": "CASH"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["preorder"]["payment_state"], "PAID")
        self.assertEqual(response.data["preorder"]["balance"], "0.00")


class SearchAPITests(PreOrderAPITestCase):
    def test_list(self):
        for _ in range(21):
            make_preorder(self.manager)
        target = make_preorder(
            self.manager, customer=self.customer, product=self.product
        )
        response = self.client.get(LIST_URL)
        self.assertEqual(response.data["count"], 22)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertEqual(response.data["results"][0]["id"], target.pk)
        self.assertNotIn("notes", response.data["results"][0])
        response = self.client.get(
            LIST_URL, {"search": "0917 123", "product": self.product.pk}
        )
        self.assertEqual([o["id"] for o in response.data["results"]], [target.pk])

    def test_empty_and_invalid(self):
        response = self.client.get(LIST_URL, {"search": "nothing"})
        self.assertEqual(response.data["count"], 0)
        response = self.client.get(LIST_URL, {"overdue": "maybe"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("overdue", response.data)

    def test_query_count_constant(self):
        def count():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(LIST_URL).status_code, 200)
            return len(ctx.captured_queries)

        make_preorder(self.manager)
        count()  # warm the user's permission cache
        few = count()
        for _ in range(10):
            make_payment(make_preorder(self.manager), "10.00")
        self.assertEqual(count(), few)


class CancelHistoryAPITests(PreOrderAPITestCase):
    def setUp(self):
        super().setUp()
        self.preorder = make_preorder(self.manager)
        self.url = url("preorder-cancel", self.preorder)

    def test_cancel(self):
        response = self.client.post(
            self.url, {"reason": "Supplier discontinued"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], S.CANCELLED)
        self.assertEqual(response.data["cancelled_by"]["id"], self.manager.pk)
        self.assertEqual(
            self.client.post(self.url, {"reason": "again"}, format="json").status_code,
            400,
        )

    def test_cancel_errors(self):
        for data in ({}, {"reason": ""}, {"reason": "  "}):
            with self.subTest(data=data):
                self.assertEqual(
                    self.client.post(self.url, data, format="json").status_code, 400
                )
        self.assertEqual(
            self.client.post(
                url("preorder-cancel", 999999), {"reason": "x"}, format="json"
            ).status_code,
            404,
        )
        self.as_user(self.staff)
        self.assertEqual(
            self.client.post(self.url, {"reason": "x"}, format="json").status_code, 403
        )

    def test_history(self):
        make_payment(self.preorder, "100.00")
        response = self.client.get(url("preorder-history", self.preorder))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([e["type"] for e in response.data], ["CREATED", "PAYMENT"])
        self.assertEqual(
            self.client.get(url("preorder-history", 999999)).status_code, 404
        )
