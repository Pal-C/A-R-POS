
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.models import Product
from inventory.models import InventoryMovement
from inventory.services import (
    adjust_stock,
    restock_product,
    reverse_movement,
)

User = get_user_model()


class InventoryServiceTests(TestCase):

    def setUp(self):
        """
        Runs before every test.

        Creates a test user and a sample product
        with an initial stock quantity of 10.
        """

        self.user = User.objects.create_user(
            username="testadmin",
            password="testpassword123",
        )

        self.product = Product.objects.create(
            sku="TEST-001",
            name="Test Badminton Racket",
            category=Product.Category.RACKET,
            selling_price="4500.00",
            cost_price="3200.00",
            stock_quantity=10,
            low_stock_threshold=3,
        )

    # ------------------------------------------
    # RESTOCK TESTS
    # ------------------------------------------

    def test_restock_increases_stock(self):
        movement = restock_product(
            product_id=self.product.id,
            quantity_received=5,
            created_by=self.user,
            reason="Supplier delivery",
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 15)
        self.assertEqual(movement.quantity_change, 5)
        self.assertEqual(movement.quantity_before, 10)
        self.assertEqual(movement.quantity_after, 15)
        self.assertEqual(
            movement.movement_type,
            InventoryMovement.MovementType.RESTOCK,
        )

    def test_restock_creates_movement_record(self):
        initial_count = InventoryMovement.objects.count()

        restock_product(
            product_id=self.product.id,
            quantity_received=5,
            created_by=self.user,
            reason="Supplier delivery",
        )

        self.assertEqual(
            InventoryMovement.objects.count(),
            initial_count + 1,
        )

    def test_restock_rejects_zero_or_negative_quantity(self):
        with self.assertRaises(ValidationError):
            restock_product(
                product_id=self.product.id,
                quantity_received=0,
                created_by=self.user,
            )

        with self.assertRaises(ValidationError):
            restock_product(
                product_id=self.product.id,
                quantity_received=-5,
                created_by=self.user,
            )

    # ------------------------------------------
    # STOCK ADJUSTMENT TESTS
    # ------------------------------------------

    def test_adjust_stock_increases_stock(self):
        movement = adjust_stock(
            product_id=self.product.id,
            quantity_change=3,
            reason="Physical inventory correction",
            created_by=self.user,
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 13)
        self.assertEqual(
            movement.movement_type,
            InventoryMovement.MovementType.ADJUSTMENT_IN,
        )

    def test_adjust_stock_decreases_stock(self):
        movement = adjust_stock(
            product_id=self.product.id,
            quantity_change=-2,
            reason="Damaged stock found during counting",
            created_by=self.user,
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 8)
        self.assertEqual(
            movement.movement_type,
            InventoryMovement.MovementType.ADJUSTMENT_OUT,
        )

    def test_adjust_stock_requires_reason(self):
        with self.assertRaises(ValidationError):
            adjust_stock(
                product_id=self.product.id,
                quantity_change=-2,
                reason="",
                created_by=self.user,
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    # ------------------------------------------
    # NEGATIVE STOCK TESTS
    # ------------------------------------------

    def test_stock_cannot_become_negative(self):
        with self.assertRaises(ValidationError):
            adjust_stock(
                product_id=self.product.id,
                quantity_change=-15,
                reason="Testing insufficient stock",
                created_by=self.user,
            )

        self.product.refresh_from_db()

        # Stock must remain unchanged.
        self.assertEqual(self.product.stock_quantity, 10)

        # No movement should have been recorded.
        self.assertEqual(InventoryMovement.objects.count(), 0)

    # ------------------------------------------
    # REVERSAL TESTS
    # ------------------------------------------

    def test_reverse_movement_restores_previous_stock(self):
        original = adjust_stock(
            product_id=self.product.id,
            quantity_change=-3,
            reason="Test stock adjustment",
            created_by=self.user,
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)

        reversal = reverse_movement(
            movement_id=original.id,
            created_by=self.user,
            reason="Correction of previous adjustment",
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(reversal.quantity_change, 3)
        self.assertEqual(
            reversal.movement_type,
            InventoryMovement.MovementType.REVERSAL,
        )
        self.assertEqual(reversal.reversal_of_id, original.id)

    def test_movement_cannot_be_reversed_twice(self):
        original = adjust_stock(
            product_id=self.product.id,
            quantity_change=-3,
            reason="Test stock adjustment",
            created_by=self.user,
        )

        reverse_movement(
            movement_id=original.id,
            created_by=self.user,
            reason="First reversal",
        )

        with self.assertRaises(ValidationError):
            reverse_movement(
                movement_id=original.id,
                created_by=self.user,
                reason="Second reversal",
            )

        self.product.refresh_from_db()

        # The second reversal must not change stock again.
        self.assertEqual(self.product.stock_quantity, 10)

    # ------------------------------------------
    # TRANSACTION ROLLBACK TEST
    # ------------------------------------------

    def test_stock_update_rolls_back_if_movement_creation_fails(self):
        with patch.object(
            InventoryMovement.objects,
            "create",
            side_effect=RuntimeError("Simulated database failure"),
        ):
            with self.assertRaises(RuntimeError):
                restock_product(
                    product_id=self.product.id,
                    quantity_received=5,
                    created_by=self.user,
                    reason="Testing rollback",
                )

        self.product.refresh_from_db()

        # The stock update should have been rolled back.
        self.assertEqual(self.product.stock_quantity, 10)

        # No movement should have been saved.
        self.assertEqual(InventoryMovement.objects.count(), 0)
