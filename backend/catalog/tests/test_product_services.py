"""Product services (research R7, contracts/products-api.md)."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from catalog.models import Product, ProductEvent
from catalog.services import (
    ProductConflict,
    create_product,
    deactivate_product,
    reactivate_product,
    update_product,
)
from catalog.tests.helpers import COST, STOCK, grant
from inventory.models import InventoryMovement
from inventory.services import adjust_stock
from sales.tests.factories import make_product, make_user


def create_data(**overrides):
    data = {
        "sku": "YNX-BG66-UM",
        "name": "BG66 Ultimax",
        "category": Product.Category.ACCESSORIES,
        "selling_price": Decimal("450.00"),
        "cost_price": Decimal("320.00"),
        "model": "  BG66  ",
        "supplier": " Yonex Philippines ",
    }
    data.update(overrides)
    return data


class CreateProductTests(TestCase):
    def setUp(self):
        self.user = grant(make_user(), COST)

    def test_creates_product_and_created_event_without_stock(self):
        product = create_product(user=self.user, data=create_data())

        self.assertEqual(product.stock_quantity, 0)
        self.assertEqual(product.model, "BG66")
        self.assertEqual(product.supplier, "Yonex Philippines")
        event = product.events.get()
        self.assertEqual(event.action, ProductEvent.Action.CREATED)
        self.assertEqual(event.performed_by, self.user)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_initial_stock_is_recorded_as_a_restock(self):
        product = create_product(user=self.user, data=create_data(), initial_stock=89)

        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 89)
        movement = InventoryMovement.objects.get(product=product)
        self.assertEqual(movement.movement_type, InventoryMovement.MovementType.RESTOCK)
        self.assertEqual(movement.quantity_change, 89)
        self.assertEqual(movement.reason, "Initial stock")
        self.assertEqual(movement.created_by, self.user)

    def test_negative_initial_stock_is_rejected_and_nothing_is_saved(self):
        with self.assertRaises(ValidationError):
            create_product(user=self.user, data=create_data(), initial_stock=-1)

        self.assertFalse(Product.objects.exists())


class UpdateProductTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.manager = grant(make_user(), COST, STOCK)
        self.product = make_product(
            selling_price=Decimal("450.00"),
            cost_price=Decimal("320.00"),
            stock_quantity=89,
        )

    def update(
        self, changes, expected=None, reason="Supplier price increase", user=None
    ):
        if expected is None:
            expected = {field: getattr(self.product, field) for field in changes}
        return update_product(
            product_id=self.product.pk,
            user=user or self.manager,
            changes=changes,
            expected=expected,
            reason=reason,
        )

    def test_writes_one_event_with_only_the_changed_fields(self):
        self.update({"selling_price": Decimal("480.00"), "name": self.product.name})

        event = self.product.events.get()
        self.assertEqual(event.action, ProductEvent.Action.UPDATED)
        self.assertEqual(event.changes, {"selling_price": ["450.00", "480.00"]})
        self.assertEqual(event.reason, "Supplier price increase")
        self.product.refresh_from_db()
        self.assertEqual(self.product.selling_price, Decimal("480.00"))

    def test_stock_change_writes_an_adjustment_with_the_same_reason(self):
        self.update({"stock_quantity": 85}, reason="Recount")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 85)
        movement = InventoryMovement.objects.get(product=self.product)
        self.assertEqual(
            movement.movement_type, InventoryMovement.MovementType.ADJUSTMENT_OUT
        )
        self.assertEqual(movement.quantity_change, -4)
        self.assertEqual(movement.reason, "Recount")
        event = self.product.events.get()
        self.assertEqual(
            event.changes, {"stock_quantity": [89, 85], "movement_id": movement.pk}
        )

    def test_stock_increase_is_an_adjustment_in(self):
        self.update({"stock_quantity": 95}, reason="Found a box")

        movement = InventoryMovement.objects.get(product=self.product)
        self.assertEqual(
            movement.movement_type, InventoryMovement.MovementType.ADJUSTMENT_IN
        )

    def test_rejects_blank_reason_empty_changes_and_missing_expected(self):
        cases = [
            ({"name": "New"}, {"name": self.product.name}, "  ", "reason"),
            ({}, {}, "Reason", "changes"),
            ({"name": "New"}, {}, "Reason", "expected"),
            (
                {"name": self.product.name},
                {"name": self.product.name},
                "Reason",
                "changes",
            ),
        ]
        for changes, expected, reason, key in cases:
            with self.subTest(key=key, changes=changes):
                with self.assertRaises(ValidationError) as ctx:
                    self.update(changes, expected=expected, reason=reason)
                self.assertIn(key, ctx.exception.message_dict)
        self.assertFalse(ProductEvent.objects.exists())

    def test_conflict_when_a_changed_field_was_changed_by_someone_else(self):
        Product.objects.filter(pk=self.product.pk).update(
            selling_price=Decimal("470.00")
        )

        with self.assertRaises(ProductConflict) as ctx:
            self.update(
                {"selling_price": Decimal("480.00")},
                expected={"selling_price": "450.00"},
            )

        self.assertEqual(ctx.exception.current, {"selling_price": "470.00"})
        self.assertFalse(ProductEvent.objects.exists())

    def test_no_conflict_when_only_an_unchanged_field_moved(self):
        adjust_stock(
            product_id=self.product.pk,
            quantity_change=-2,
            reason="Sold",
            created_by=self.user,
        )

        self.update(
            {"selling_price": Decimal("480.00")}, expected={"selling_price": "450.00"}
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.selling_price, Decimal("480.00"))
        self.assertEqual(self.product.stock_quantity, 87)

    def test_stock_conflict_after_a_concurrent_sale(self):
        adjust_stock(
            product_id=self.product.pk,
            quantity_change=-2,
            reason="Sold",
            created_by=self.user,
        )

        with self.assertRaises(ProductConflict) as ctx:
            self.update({"stock_quantity": 85}, expected={"stock_quantity": 89})

        self.assertEqual(ctx.exception.current, {"stock_quantity": 87})

    def test_stock_change_requires_adjust_stock_permission(self):
        with self.assertRaises(PermissionDenied):
            self.update({"stock_quantity": 85}, user=self.user)

    def test_cost_change_requires_view_cost_permission(self):
        with self.assertRaises(PermissionDenied):
            self.update({"cost_price": Decimal("300.00")}, user=self.user)

    def test_other_fields_need_no_special_permission(self):
        self.update({"supplier": "  New Supplier "}, user=self.user)

        self.product.refresh_from_db()
        self.assertEqual(self.product.supplier, "New Supplier")


class ActivationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()

    def test_deactivate_and_reactivate_write_events(self):
        deactivate_product(
            product_id=self.product.pk, user=self.user, reason="Discontinued"
        )
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

        reactivate_product(
            product_id=self.product.pk, user=self.user, reason="Back in range"
        )
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)

        actions = list(
            self.product.events.order_by("id").values_list("action", "reason")
        )
        self.assertEqual(
            actions,
            [("DEACTIVATED", "Discontinued"), ("REACTIVATED", "Back in range")],
        )

    def test_reason_is_required(self):
        for func in (deactivate_product, reactivate_product):
            with self.subTest(func=func.__name__), self.assertRaises(ValidationError):
                func(product_id=self.product.pk, user=self.user, reason=" ")

    def test_rejects_the_already_in_state_case(self):
        with self.assertRaises(ValidationError):
            reactivate_product(product_id=self.product.pk, user=self.user, reason="x")
        deactivate_product(product_id=self.product.pk, user=self.user, reason="x")
        with self.assertRaises(ValidationError):
            deactivate_product(product_id=self.product.pk, user=self.user, reason="x")


class ReviewFixTests(TestCase):
    """Regression tests for the 005 code-review findings."""

    def setUp(self):
        self.user = grant(make_user(), COST, STOCK)
        self.product = make_product(sku="AAA-1")
        self.other = make_product(sku="BBB-2")

    def test_duplicate_sku_on_create_is_a_validation_error_not_a_crash(self):
        # The serializer check can be raced; the DB constraint must map to a 400.
        with self.assertRaises(ValidationError) as ctx:
            create_product(user=self.user, data=create_data(sku="AAA-1"))

        self.assertIn("sku", ctx.exception.message_dict)

    def test_duplicate_sku_on_update_is_a_validation_error_not_a_crash(self):
        with self.assertRaises(ValidationError) as ctx:
            update_product(
                product_id=self.other.pk,
                user=self.user,
                changes={"sku": "AAA-1"},
                expected={"sku": "BBB-2"},
                reason="Relabel",
            )

        self.assertIn("sku", ctx.exception.message_dict)
        self.assertFalse(ProductEvent.objects.exists())

    def test_edit_cannot_change_active_state(self):
        # Activation goes through deactivate/reactivate (confirmation + right event).
        with self.assertRaises(ValidationError) as ctx:
            update_product(
                product_id=self.product.pk,
                user=self.user,
                changes={"is_active": False},
                expected={"is_active": True},
                reason="Typo",
            )

        self.assertIn("changes", ctx.exception.message_dict)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)
