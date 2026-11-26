
from rest_framework import serializers

from catalog.models import Product
from customers.models import Customer
from preorders.models import PreOrder
from sales.models import Payment, Sale, SaleItem
from stringing.models import StringingOrder


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )
    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True,
    )
    line_subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    line_total = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    gross_profit = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "quantity",
            "unit_selling_price",
            "unit_cost_price",
            "discount_amount",
            "line_subtotal",
            "line_total",
            "gross_profit",
            "created_at",
        ]
        read_only_fields = fields


class SaleListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source="customer.full_name",
        read_only=True,
        allow_null=True,
    )
    created_by_name = serializers.CharField(
        source="created_by.username",
        read_only=True,
    )
    amount_paid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    balance = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Sale
        fields = [
            "id",
            "sale_number",
            "customer",
            "customer_name",
            "created_by",
            "created_by_name",
            "subtotal",
            "discount_amount",
            "total_amount",
            "amount_paid",
            "balance",
            "status",
            "created_at",
            "finalized_at",
            "cancelled_at",
        ]
        read_only_fields = fields


class SaleDetailSerializer(SaleListSerializer):
    items = SaleItemSerializer(many=True, read_only=True)

    class Meta(SaleListSerializer.Meta):
        fields = SaleListSerializer.Meta.fields + [
            "items",
            "cancellation_reason",
            "cancelled_by",
            "updated_at",
        ]


class SaleItemCreateSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(
        source="product",
        queryset=Product.objects.filter(is_active=True),
    )
    quantity = serializers.IntegerField(min_value=1)
    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        default=0,
    )


class SaleCreateSerializer(serializers.Serializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer",
        queryset=Customer.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        default=0,
    )
    items = SaleItemCreateSerializer(many=True)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError(
                "A sale must contain at least one item."
            )
        return items

    def validate(self, attrs):
        product_ids = [
            item["product"].pk
            for item in attrs["items"]
        ]

        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError({
                "items": (
                    "Each product should only appear once. "
                    "Combine quantities for duplicate products."
                )
            })

        return attrs

    def create(self, validated_data):
        from sales.services import create_draft_sale

        items = validated_data.pop("items")

        return create_draft_sale(
            user=self.context["request"].user,
            items=items,
            **validated_data,
        )


class PaymentSerializer(serializers.ModelSerializer):
    received_by_name = serializers.CharField(
        source="received_by.username",
        read_only=True,
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "sale",
            "stringing_order",
            "preorder",
            "amount",
            "payment_method",
            "payment_type",
            "status",
            "payment_date",
            "reference_number",
            "notes",
            "received_by",
            "received_by_name",
            "created_at",
        ]
        read_only_fields = fields


class PaymentCreateSerializer(serializers.Serializer):
    sale = serializers.PrimaryKeyRelatedField(
        queryset=Sale.objects.all(),
        required=False,
        allow_null=True,
    )
    stringing_order = serializers.PrimaryKeyRelatedField(
        queryset=StringingOrder.objects.all(),
        required=False,
        allow_null=True,
    )
    preorder = serializers.PrimaryKeyRelatedField(
        queryset=PreOrder.objects.all(),
        required=False,
        allow_null=True,
    )

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
    )
    payment_method = serializers.ChoiceField(
        choices=Payment.Method.choices,
    )
    payment_type = serializers.ChoiceField(
        choices=Payment.PaymentType.choices,
        default=Payment.PaymentType.RECEIPT,
    )
    reference_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        targets = [
            attrs.get("sale"),
            attrs.get("stringing_order"),
            attrs.get("preorder"),
        ]

        if sum(target is not None for target in targets) != 1:
            raise serializers.ValidationError(
                "A payment must belong to exactly one sale, "
                "stringing order, or preorder."
            )

        return attrs

    def create(self, validated_data):
        from sales.services import record_payment

        return record_payment(
            user=self.context["request"].user,
            **validated_data,
        )
