"""Validate incoming data and format API responses"""

from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    is_out_of_stock = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()

    class Meta:
        model = Product

        fields = [
            "id",
            "sku",
            "name",
            "category",
            "subcategory",
            "brand",
            "variant_description",
            "description",
            "selling_price",
            "cost_price",
            "stock_quantity",
            "low_stock_threshold",
            "is_low_stock",
            "is_out_of_stock",
            "stock_status",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "stock_quantity",
            "is_low_stock",
            "is_out_of_stock",
            "stock_status",
            "created_at",
            "updated_at",
        ]

    def get_is_out_of_stock(self, obj):
        return obj.stock_quantity == 0

    def get_stock_status(self, obj):
        if obj.stock_quantity == 0:
            return "OUT_OF_STOCK"

        if obj.stock_quantity <= obj.low_stock_threshold:
            return "LOW_STOCK"

        return "IN_STOCK"

    def validate_sku(self, value):
        value = value.strip()

        queryset = Product.objects.filter(sku__iexact=value)

        # Exclude the current product when editing.
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "A product with this SKU already exists."
            )

        return value

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Product name cannot be empty."
            )

        return value

    def validate(self, attrs):
        selling_price = attrs.get(
            "selling_price",
            getattr(self.instance, "selling_price", None),
        )

        cost_price = attrs.get(
            "cost_price",
            getattr(self.instance, "cost_price", None),
        )

        if selling_price is not None and selling_price < 0:
            raise serializers.ValidationError({
                "selling_price": "Selling price cannot be negative."
            })

        if cost_price is not None and cost_price < 0:
            raise serializers.ValidationError({
                "cost_price": "Cost price cannot be negative."
            })

        return attrs
