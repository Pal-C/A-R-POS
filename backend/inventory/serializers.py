
from rest_framework import serializers

from catalog.models import Product
from inventory.models import InventoryMovement


class InventoryMovementSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for inventory movement records.

    Movement records are created through inventory services,
    not directly through the API serializer.
    """

    product_id = serializers.IntegerField(
        source="product.id",
        read_only=True
    )
    product_name = serializers.CharField(
        source="product.name",
        read_only=True
    )
    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True
    )

    created_by_id = serializers.IntegerField(
        source="created_by.id",
        read_only=True
    )
    created_by = serializers.CharField(
        source="created_by.username",
        read_only=True
    )

    class Meta:
        model = InventoryMovement
        fields = [
            "id",
            "product_id",
            "product_name",
            "product_sku",
            "sale_item",
            "movement_type",
            "quantity_change",
            "quantity_before",
            "quantity_after",
            "reason",
            "reference_number",
            "reversal_of",
            "created_by_id",
            "created_by",
            "movement_date",
        ]
        read_only_fields = fields


class RestockSerializer(serializers.Serializer):
    """
    Validates input for receiving new stock from suppliers.
    """

    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product"
    )

    quantity_received = serializers.IntegerField(
        min_value=1
    )

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )

    reference_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        default=""
    )


class StockAdjustmentSerializer(serializers.Serializer):
    """
    Validates manual stock increases and decreases.

    Positive quantity_change = stock increase.
    Negative quantity_change = stock decrease.
    """

    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product"
    )

    quantity_change = serializers.IntegerField()

    reason = serializers.CharField(
        required=True,
        allow_blank=False
    )

    reference_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        default=""
    )

    def validate_quantity_change(self, value):
        if value == 0:
            raise serializers.ValidationError(
                "Adjustment quantity cannot be zero."
            )

        return value

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "A reason is required for manual stock adjustments."
            )

        return value.strip()


class ReverseMovementSerializer(serializers.Serializer):
    """
    Validates the information required to reverse an existing
    inventory movement.
    """

    reason = serializers.CharField(
        required=True,
        allow_blank=False
    )

    reference_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        default=""
    )

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "A reason is required when reversing a movement."
            )

        return value.strip()
