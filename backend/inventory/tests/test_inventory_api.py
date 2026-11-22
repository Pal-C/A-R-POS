
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Product
from inventory.models import InventoryMovement
from inventory.services import restock_product


User = get_user_model()


class InventoryAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="inventory_admin",
            password="testpassword123"
        )
        self.client.force_authenticate(user=self.user)

        self.product = self.create_product(
            sku="RKT-001",
            name="Badminton Racket",
            stock_quantity=10,
            low_stock_threshold=5
        )

    def create_product(
        self,
        *,
        sku,
        name,
        stock_quantity=0,
        low_stock_threshold=5,
        is_active=True
    ):
        """
        Helper method for creating products used by API tests.

        Direct stock setup is used only for test fixtures.
        Actual API stock changes must go through inventory services.
        """

        return Product.objects.create(
            sku=sku,
            name=name,
            category=Product.Category.RACKET,
            selling_price=1500.00,
            cost_price=1000.00,
            stock_quantity=stock_quantity,
            low_stock_threshold=low_stock_threshold,
            is_active=is_active
        )

    # --------------------------------------------------
    # MOVEMENT HISTORY
    # --------------------------------------------------

    def test_list_inventory_movements(self):
        restock_product(
            product_id=self.product.id,
            quantity_received=10,
            created_by=self.user,
            reason="Supplier delivery",
            reference_number="PO-001"
        )

        url = reverse("inventory-movement-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["movement_type"],
            InventoryMovement.MovementType.RESTOCK
        )
        self.assertEqual(results[0]["quantity_change"], 10)
        self.assertEqual(results[0]["quantity_before"], 10)
        self.assertEqual(results[0]["quantity_after"], 20)
        self.assertEqual(results[0]["product_id"], self.product.id)
        self.assertEqual(results[0]["created_by"], self.user.username)

    def test_retrieve_inventory_movement(self):
        movement = restock_product(
            product_id=self.product.id,
            quantity_received=5,
            created_by=self.user,
            reason="Supplier delivery"
        )

        url = reverse(
            "inventory-movement-detail",
            kwargs={"pk": movement.id}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], movement.id)
        self.assertEqual(response.data["quantity_change"], 5)

    def test_filter_movements_by_product(self):
        another_product = self.create_product(
            sku="SHU-001",
            name="Shuttlecock",
        )

        restock_product(
            product_id=self.product.id,
            quantity_received=5,
            created_by=self.user
        )

        restock_product(
            product_id=another_product.id,
            quantity_received=10,
            created_by=self.user
        )

        url = reverse("inventory-movement-list")
        response = self.client.get(
            url,
            {"product_id": self.product.id}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["product_id"],
            self.product.id
        )

    def test_filter_movements_by_type(self):
        restock_product(
            product_id=self.product.id,
            quantity_received=5,
            created_by=self.user
        )

        url = reverse("inventory-movement-list")
        response = self.client.get(
            url,
            {"movement_type": "RESTOCK"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_invalid_movement_type_returns_400(self):
        url = reverse("inventory-movement-list")
        response = self.client.get(
            url,
            {"movement_type": "INVALID"}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_movement_list_does_not_allow_post(self):
        url = reverse("inventory-movement-list")
        response = self.client.post(url, {})

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_movement_detail_does_not_allow_patch_or_delete(self):
        movement = restock_product(
            product_id=self.product.id,
            quantity_received=5,
            created_by=self.user
        )

        url = reverse(
            "inventory-movement-detail",
            kwargs={"pk": movement.id}
        )

        patch_response = self.client.patch(
            url,
            {"quantity_change": 100}
        )
        delete_response = self.client.delete(url)

        self.assertEqual(
            patch_response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )
        self.assertEqual(
            delete_response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

        movement.refresh_from_db()
        self.assertEqual(movement.quantity_change, 5)

    # --------------------------------------------------
    # RESTOCK
    # --------------------------------------------------

    def test_restock_product_successfully(self):
        url = reverse("inventory-restock")

        payload = {
            "product_id": self.product.id,
            "quantity_received": 20,
            "reason": "New supplier delivery",
            "reference_number": "PO-2026-001"
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 30)

        self.assertEqual(
            InventoryMovement.objects.filter(
                product=self.product,
                movement_type=InventoryMovement.MovementType.RESTOCK
            ).count(),
            1
        )

        movement = InventoryMovement.objects.get(
            product=self.product,
            movement_type=InventoryMovement.MovementType.RESTOCK
        )

        self.assertEqual(movement.quantity_change, 20)
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(movement.reason, "New supplier delivery")
        self.assertEqual(movement.reference_number, "PO-2026-001")

    def test_restock_rejects_zero_quantity(self):
        url = reverse("inventory-restock")

        response = self.client.post(
            url,
            {
                "product_id": self.product.id,
                "quantity_received": 0
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(InventoryMovement.objects.count(), 0)

    def test_restock_rejects_negative_quantity(self):
        url = reverse("inventory-restock")

        response = self.client.post(
            url,
            {
                "product_id": self.product.id,
                "quantity_received": -5
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(InventoryMovement.objects.count(), 0)

    def test_restock_rejects_nonexistent_product(self):
        url = reverse("inventory-restock")

        response = self.client.post(
            url,
            {
                "product_id": 99999,
                "quantity_received": 5
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(InventoryMovement.objects.count(), 0)

    # --------------------------------------------------
    # STOCK ADJUSTMENTS
    # --------------------------------------------------

    def test_adjust_stock_increase_successfully(self):
        url = reverse("inventory-adjustment")

        response = self.client.post(
            url,
            {
                "product_id": self.product.id,
                "quantity_change": 5,
                "reason": "Stock count correction"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 15)

        movement = InventoryMovement.objects.get(
            product=self.product
        )

        self.assertEqual(
            movement.movement_type,
            InventoryMovement.MovementType.ADJUSTMENT_IN
        )
        self.assertEqual(movement.quantity_change, 5)

    def test_adjust_stock_decrease_successfully(self):
        url = reverse("inventory-adjustment")

        response = self.client.post(
            url,
            {
                "product_id": self.product.id,
                "quantity_change": -3,
                "reason": "Damaged stock correction"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)

        movement = InventoryMovement.objects.get(
            product=self.product
        )

        self.assertEqual(
            movement.movement_type,
            InventoryMovement.MovementType.ADJUSTMENT_OUT
        )
        self.assertEqual(movement.quantity_change, -3)

    def test_adjustment_rejects_zero_quantity(self):
        url = reverse("inventory-adjustment")

        response = self.client.post(
            url,
            {
                "product_id": self.product.id,
                "quantity_change": 0,
                "reason": "Stock correction"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(InventoryMovement.objects.count(), 0)

    def test_adjustment_requires_reason(self):
        url = reverse("inventory-adjustment")

        response = self.client.post(
            url,
            {
                "product_id": self.product.id,
                "quantity_change": 5,
                "reason": "   "
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(InventoryMovement.objects.count(), 0)

    def test_adjustment_rejects_insufficient_stock(self):
        url = reverse("inventory-adjustment")

        response = self.client.post(
            url,
            {
                "product_id": self.product.id,
                "quantity_change": -15,
                "reason": "Incorrect stock count"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(InventoryMovement.objects.count(), 0)

    # --------------------------------------------------
    # MOVEMENT REVERSAL
    # --------------------------------------------------

    def test_reverse_inventory_movement_successfully(self):
        original_movement = restock_product(
            product_id=self.product.id,
            quantity_received=5,
            created_by=self.user,
            reason="Incorrect supplier delivery record"
        )

        url = reverse(
            "inventory-movement-reverse",
            kwargs={"pk": original_movement.id}
        )

        response = self.client.post(
            url,
            {
                "reason": "Reversing incorrect restock"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

        self.assertEqual(
            InventoryMovement.objects.count(),
            2
        )

        reversal = InventoryMovement.objects.get(
            movement_type=InventoryMovement.MovementType.REVERSAL
        )

        self.assertEqual(reversal.quantity_change, -5)
        self.assertEqual(reversal.reversal_of, original_movement)
        self.assertEqual(reversal.created_by, self.user)

    def test_reverse_movement_twice_is_rejected(self):
        original_movement = restock_product(
            product_id=self.product.id,
            quantity_received=5,
            created_by=self.user
        )

        url = reverse(
            "inventory-movement-reverse",
            kwargs={"pk": original_movement.id}
        )

        first_response = self.client.post(
            url,
            {"reason": "First reversal"},
            format="json"
        )

        second_response = self.client.post(
            url,
            {"reason": "Second reversal"},
            format="json"
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED
        )
        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(InventoryMovement.objects.count(), 2)

    def test_reverse_nonexistent_movement_returns_404(self):
        url = reverse(
            "inventory-movement-reverse",
            kwargs={"pk": 99999}
        )

        response = self.client.post(
            url,
            {"reason": "Invalid reversal"},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    def test_reverse_movement_requires_reason(self):
        original_movement = restock_product(
            product_id=self.product.id,
            quantity_received=5,
            created_by=self.user
        )

        url = reverse(
            "inventory-movement-reverse",
            kwargs={"pk": original_movement.id}
        )

        response = self.client.post(
            url,
            {"reason": "   "},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 15)
        self.assertEqual(InventoryMovement.objects.count(), 1)

    # --------------------------------------------------
    # LOW STOCK AND OUT OF STOCK
    # --------------------------------------------------

    def test_low_stock_endpoint_returns_low_stock_products(self):
        low_stock_product = self.create_product(
            sku="RKT-002",
            name="Low Stock Racket",
            stock_quantity=3,
            low_stock_threshold=5
        )

        url = reverse("inventory-low-stock")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_ids = [
            item["id"] for item in response.data["results"]
        ]

        self.assertIn(low_stock_product.id, returned_ids)
        self.assertNotIn(self.product.id, returned_ids)

    def test_low_stock_endpoint_excludes_out_of_stock_products(self):
        out_of_stock_product = self.create_product(
            sku="RKT-003",
            name="Out of Stock Racket",
            stock_quantity=0
        )

        url = reverse("inventory-low-stock")
        response = self.client.get(url)

        returned_ids = [
            item["id"] for item in response.data["results"]
        ]

        self.assertNotIn(out_of_stock_product.id, returned_ids)

    def test_out_of_stock_endpoint_returns_zero_stock_products(self):
        out_of_stock_product = self.create_product(
            sku="RKT-004",
            name="Unavailable Racket",
            stock_quantity=0
        )

        url = reverse("inventory-out-of-stock")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_ids = [
            item["id"] for item in response.data["results"]
        ]

        self.assertIn(out_of_stock_product.id, returned_ids)
        self.assertNotIn(self.product.id, returned_ids)

    def test_stock_endpoints_exclude_inactive_products(self):
        inactive_low_stock = self.create_product(
            sku="RKT-005",
            name="Inactive Low Stock Racket",
            stock_quantity=2,
            is_active=False
        )

        inactive_out_of_stock = self.create_product(
            sku="RKT-006",
            name="Inactive Out of Stock Racket",
            stock_quantity=0,
            is_active=False
        )

        low_stock_response = self.client.get(
            reverse("inventory-low-stock")
        )
        out_of_stock_response = self.client.get(
            reverse("inventory-out-of-stock")
        )

        low_stock_ids = [
            item["id"] for item in low_stock_response.data["results"]
        ]
        out_of_stock_ids = [
            item["id"] for item in out_of_stock_response.data["results"]
        ]

        self.assertNotIn(inactive_low_stock.id, low_stock_ids)
        self.assertNotIn(inactive_out_of_stock.id, out_of_stock_ids)

    # --------------------------------------------------
    # INVENTORY SUMMARY
    # --------------------------------------------------

    def test_inventory_summary_returns_correct_values(self):
        self.create_product(
            sku="RKT-007",
            name="Low Stock Racket",
            stock_quantity=3,
            low_stock_threshold=5
        )

        self.create_product(
            sku="RKT-008",
            name="Out of Stock Racket",
            stock_quantity=0
        )

        self.create_product(
            sku="RKT-009",
            name="Inactive Racket",
            stock_quantity=100,
            is_active=False
        )

        url = reverse("inventory-summary")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data["active_product_count"], 3)
        self.assertEqual(response.data["total_units_in_stock"], 13)
        self.assertEqual(response.data["low_stock_count"], 1)
        self.assertEqual(response.data["out_of_stock_count"], 1)

    # --------------------------------------------------
    # AUTHENTICATION
    # --------------------------------------------------

    def test_unauthenticated_user_cannot_access_inventory(self):
        self.client.force_authenticate(user=None)

        endpoints = [
            reverse("inventory-movement-list"),
            reverse("inventory-restock"),
            reverse("inventory-adjustment"),
            reverse("inventory-low-stock"),
            reverse("inventory-out-of-stock"),
            reverse("inventory-summary"),
        ]

        for url in endpoints:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    status.HTTP_403_FORBIDDEN
                )
