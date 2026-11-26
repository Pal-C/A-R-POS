"""
Story-level run through the pre-order API (quickstart.md): create with a
deposit → order from supplier → arrival → pay → fulfill; a second order
cancelled and refunded; stock never changes.
"""

from datetime import timedelta

from django.urls import reverse
from rest_framework.test import APITestCase

from inventory.models import InventoryMovement
from preorders.selectors import store_today
from preorders.tests.factories import (
    ALL_PERMISSIONS,
    make_customer,
    make_product,
    make_user,
)


class PreOrderWorkflowTests(APITestCase):
    def setUp(self):
        self.cashier = make_user(username="cashier", perms=["sales.record_payment"])
        self.manager = make_user(username="manager", perms=ALL_PERMISSIONS)
        self.customer = make_customer(
            full_name="Ana Reyes", phone_number="0917 123 4567"
        )
        self.product = make_product(
            name="Astrox 100ZZ", sku="RKT-AX100", stock_quantity=5
        )

    def call(self, method, url, data=None, expected=200):
        response = getattr(self.client, method)(url, data, format="json")
        self.assertEqual(
            response.status_code, expected, getattr(response, "data", None)
        )
        return response.data

    def u(self, name, pk):
        return reverse(name, kwargs={"pk": pk})

    def test_preorder_lifecycle(self):
        list_url = reverse("preorder-list-create")
        arrivals = reverse(
            "preorder-product-arrivals", kwargs={"product_id": self.product.pk}
        )
        self.client.force_authenticate(self.cashier)

        # Take the pre-order with a deposit (US1, US2).
        order = self.call(
            "post",
            list_url,
            {
                "customer": self.customer.pk,
                "product": self.product.pk,
                "quantity": 2,
                "agreed_unit_price": "5000.00",
                "expected_arrival_date": (
                    store_today() + timedelta(days=21)
                ).isoformat(),
            },
            201,
        )
        oid = order["id"]
        pay = self.u("preorder-payments", oid)
        deposit = self.call(
            "post", pay, {"amount": "4000.00", "payment_method": "CASH"}, 201
        )
        self.assertEqual(deposit["preorder"]["balance"], "6000.00")
        self.call("post", pay, {"amount": "7000.00", "payment_method": "CASH"}, 400)

        # Order from supplier and receive the delivery (US3).
        self.call("post", self.u("preorder-status", oid), {"status": "ORDERED"})
        other = self.call(
            "post",
            list_url,
            {"customer": self.customer.pk, "product": self.product.pk, "quantity": 1},
            201,
        )
        self.call("post", self.u("preorder-status", other["id"]), {"status": "ORDERED"})
        arrived = self.call("post", arrivals, {"received_quantity": 2})
        self.assertEqual([o["id"] for o in arrived["marked"]], [oid])
        self.assertEqual(arrived["units_left"], 0)

        # Fulfill once paid (US4).
        fulfill = self.u("preorder-fulfill", oid)
        self.call("post", fulfill, None, 400)
        self.call("post", pay, {"amount": "6000.00", "payment_method": "GCASH"}, 201)
        done = self.call("post", fulfill)
        self.assertEqual(done["status"], "FULFILLED")
        self.call("post", pay, {"amount": "1.00", "payment_method": "CASH"}, 400)

        # Search (US5).
        found = self.call(
            "get", list_url, {"search": "RKT-AX100", "status": "FULFILLED"}
        )
        self.assertEqual([o["id"] for o in found["results"]], [oid])

        # Cancel the second order and refund its deposit (US6).
        other_pay = self.u("preorder-payments", other["id"])
        self.call(
            "post", other_pay, {"amount": "1000.00", "payment_method": "CASH"}, 201
        )
        cancel = self.u("preorder-cancel", other["id"])
        self.call("post", cancel, {"reason": "Changed mind"}, 403)
        self.client.force_authenticate(self.manager)
        cancelled = self.call("post", cancel, {"reason": "Changed mind"})
        self.assertEqual(cancelled["refund_due"], "1000.00")
        refunded = self.call(
            "post",
            other_pay,
            {
                "amount": "1000.00",
                "payment_method": "CASH",
                "payment_type": "REFUND",
                "reason": "Cancelled",
            },
            201,
        )
        self.assertEqual(refunded["preorder"]["refund_due"], "0.00")

        history = self.call("get", self.u("preorder-history", oid))
        self.assertEqual(
            [e["type"] for e in history],
            [
                "CREATED",
                "PAYMENT",
                "STATUS_CHANGED",
                "STATUS_CHANGED",
                "PAYMENT",
                "STATUS_CHANGED",
            ],
        )

        # Pre-orders never touch stock (Q1).
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertFalse(InventoryMovement.objects.exists())
