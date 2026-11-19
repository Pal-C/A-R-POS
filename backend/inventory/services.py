
from django.db import transaction
from django.core.exceptions import ValidationError

from catalog.models import Product
from inventory.models import InventoryMovement


@transaction.atomic
def change_stock(
    *,
    product_id,
    quantity_change,
    movement_type,
    user,
    reason="",
    sale_item=None,
    reference_number="",
    reversal_of=None,
):
    """
    The only approved way to change a product's stock.

    Positive quantity_change = stock increase.
    Negative quantity_change = stock decrease.
    """

    if quantity_change == 0:
        raise ValidationError("Stock change cannot be zero.")

    product = Product.objects.select_for_update().get(
        pk=product_id
    )

    quantity_before = product.stock_quantity
    quantity_after = quantity_before + quantity_change

    if quantity_after < 0:
        raise ValidationError(
            f"Insufficient stock for {product.name}. "
            f"Available: {quantity_before}."
        )

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
        created_by=user,
    )

    product.stock_quantity = quantity_after
    product.save(update_fields=["stock_quantity", "updated_at"])

    return movement
