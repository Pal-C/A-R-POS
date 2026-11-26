
from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import Product
from inventory.models import InventoryMovement


class InventoryServiceError(Exception):
    """Base exception for inventory-related operations."""
    pass



@transaction.atomic
def _apply_stock_change(
    *,
    product_id,
    movement_type,
    quantity_change,
    created_by,
    reason="",
    reference_number="",
    sale_item=None,
    reversal_of=None,
):
    """
    Internal helper that applies a stock change and creates
    the corresponding InventoryMovement.

    All stock-changing service functions should use this helper.
    """

    if quantity_change == 0:
        raise ValidationError("Quantity change cannot be zero.")

    if created_by is None:
        raise ValidationError("A user must be provided for this operation.")

    # Validate that the movement type matches the direction of the change.
    increase_types = {
        InventoryMovement.MovementType.RESTOCK,
        InventoryMovement.MovementType.CUSTOMER_RETURN,
        InventoryMovement.MovementType.ADJUSTMENT_IN,
    }

    decrease_types = {
        InventoryMovement.MovementType.SALE,
        InventoryMovement.MovementType.DAMAGE,
        InventoryMovement.MovementType.ADJUSTMENT_OUT,
    }

    if movement_type in increase_types and quantity_change < 0:
        raise ValidationError(
            "This movement type must increase stock."
        )

    if movement_type in decrease_types and quantity_change > 0:
        raise ValidationError(
            "This movement type must decrease stock."
        )

    if (
        movement_type == InventoryMovement.MovementType.REVERSAL
        and reversal_of is None
    ):
        raise ValidationError(
            "A reversal must reference the original movement."
        )

    if (
        movement_type != InventoryMovement.MovementType.REVERSAL
        and reversal_of is not None
    ):
        raise ValidationError(
            "Only reversal movements can reference an original movement."
        )

    with transaction.atomic():
        # Lock the product row so simultaneous stock operations
        # cannot calculate their changes using the same old quantity.
        product = (
            Product.objects
            .select_for_update()
            .get(pk=product_id)
        )

        quantity_before = product.stock_quantity
        quantity_after = quantity_before + quantity_change

        if quantity_after < 0:
            raise ValidationError(
                f"Insufficient stock for {product.name}. "
                f"Available: {quantity_before}, "
                f"requested change: {quantity_change}."
            )

        # Update the product's current stock.
        product.stock_quantity = quantity_after
        product.save(update_fields=["stock_quantity", "updated_at"])

        # Record the stock change.
        movement = InventoryMovement.objects.create(
            product=product,
            sale_item=sale_item,
            movement_type=movement_type,
            quantity_change=quantity_change,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            reason=reason,
            reference_number=reference_number,
            reversal_of=reversal_of,
            created_by=created_by,
        )

        return movement


def restock_product(
    *,
    product_id,
    quantity_received,
    created_by,
    reason="",
    reference_number="",
):
    """
    Adds newly received supplier stock.
    """

    if quantity_received <= 0:
        raise ValidationError(
            "Quantity received must be greater than zero."
        )

    return _apply_stock_change(
        product_id=product_id,
        movement_type=InventoryMovement.MovementType.RESTOCK,
        quantity_change=quantity_received,
        created_by=created_by,
        reason=reason,
        reference_number=reference_number,
    )


def adjust_stock(
    *,
    product_id,
    quantity_change,
    reason,
    created_by,
    reference_number="",
):
    """
    Manually increases or decreases stock.

    Positive quantity_change = stock increase.
    Negative quantity_change = stock decrease.
    """

    if quantity_change == 0:
        raise ValidationError(
            "Adjustment quantity cannot be zero."
        )

    if not reason or not reason.strip():
        raise ValidationError(
            "A reason is required for manual stock adjustments."
        )

    movement_type = (
        InventoryMovement.MovementType.ADJUSTMENT_IN
        if quantity_change > 0
        else InventoryMovement.MovementType.ADJUSTMENT_OUT
    )

    return _apply_stock_change(
        product_id=product_id,
        movement_type=movement_type,
        quantity_change=quantity_change,
        created_by=created_by,
        reason=reason,
        reference_number=reference_number,
    )


def deduct_stock_for_sale(
    *,
    product_id,
    quantity_sold,
    created_by,
    sale_item,
    reference_number="",
):
    """
    Deducts stock for a sale and links the movement
    to the corresponding SaleItem.
    """

    if quantity_sold <= 0:
        raise ValidationError(
            "Quantity sold must be greater than zero."
        )

    if sale_item is None:
        raise ValidationError(
            "A sale item must be provided."
        )

    return _apply_stock_change(
        product_id=product_id,
        movement_type=InventoryMovement.MovementType.SALE,
        quantity_change=-quantity_sold,
        created_by=created_by,
        sale_item=sale_item,
        reference_number=reference_number,
        reason="Stock deducted for sale.",
    )


def reverse_movement(
    *,
    movement_id,
    created_by,
    reason,
    reference_number="",
):
    """
    Reverses a previous inventory movement by creating
    a new movement with the opposite quantity change.

    The original movement remains unchanged.
    """

    if not reason or not reason.strip():
        raise ValidationError(
            "A reason is required when reversing a movement."
        )

    if created_by is None:
        raise ValidationError(
            "A user must be provided for this operation."
        )

    with transaction.atomic():
        # Lock the original movement to prevent two simultaneous
        # requests from reversing it more than once.
        original = (
            InventoryMovement.objects
            .select_for_update()
            .get(pk=movement_id)
        )

        if original.movement_type == InventoryMovement.MovementType.REVERSAL:
            raise ValidationError(
                "A reversal movement cannot itself be reversed."
            )

        if original.reversals.exists():
            raise ValidationError(
                "This inventory movement has already been reversed."
            )

        return _apply_stock_change(
            product_id=original.product_id,
            movement_type=InventoryMovement.MovementType.REVERSAL,
            quantity_change=-original.quantity_change,
            created_by=created_by,
            reason=reason,
            reference_number=reference_number,
            reversal_of=original,
        )
