from django.conf import settings
from django.db import models

# Create your models here.

#InventoryMovement ----------------------------------

class InventoryMovement(models.Model):

    class MovementType(models.TextChoices):
        SALE = "SALE", "Sale"
        RESTOCK = "RESTOCK", "Restock"
        CUSTOMER_RETURN = "CUSTOMER_RETURN", "Customer Return"
        DAMAGE = "DAMAGE", "Damaged Goods"
        ADJUSTMENT_IN = "ADJUSTMENT_IN", "Stock Increase"
        ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Stock Decrease"
        REVERSAL = "REVERSAL", "Reversal"

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="inventory_movements"
    )

    sale_item = models.ForeignKey(
        "sales.SaleItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_movements"
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices
    )

    # Positive = stock increase; negative = stock decrease.
    quantity_change = models.IntegerField()

    quantity_before = models.PositiveIntegerField()
    quantity_after = models.PositiveIntegerField()

    reason = models.TextField(blank=True)
    reference_number = models.CharField(
        max_length=100, blank=True
    )

    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversals"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    movement_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-movement_date"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity_change=0),
                name="inventory_movement_nonzero"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    quantity_after=models.F("quantity_before")
                    + models.F("quantity_change")
                ),
                name="inventory_movement_balance_matches"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_after__gte=0),
                name="inventory_movement_no_negative_stock"
            )
        ]
        indexes = [
            models.Index(
                fields=["product", "-movement_date"],
                name="inv_product_date_idx"
            ),
        ]

    def __str__(self):
        return (
            f"{self.product.name}: "
            f"{self.quantity_change:+d}"
        )
