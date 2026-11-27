from decimal import Decimal

from rest_framework import serializers

from catalog.models import Product
from catalog.serializers import EventUserSerializer, can_view_cost
from customers.models import Customer
from preorders.models import PreOrder
from sales.models import Payment, Sale, SaleEvent, SaleItem
from stringing.models import StringingOrder

ZERO = Decimal("0.00")
MONEY = {"max_digits": 12, "decimal_places": 2}
LINE_MONEY = {"max_digits": 10, "decimal_places": 2}


# ---------------------------------------------------------------------------
# Reference fields
# ---------------------------------------------------------------------------


class ActiveProductField(serializers.PrimaryKeyRelatedField):
    """Product reference that gives a clear error for archived products."""

    default_error_messages = {
        "does_not_exist": "Product {pk_value} does not exist.",
        "inactive": "{name} is inactive and cannot be sold.",
    }

    def get_queryset(self):
        return Product.objects.all()

    def to_internal_value(self, data):
        product = super().to_internal_value(data)
        if not product.is_active:
            self.fail("inactive", name=product.name)
        return product


class ActiveCustomerField(serializers.PrimaryKeyRelatedField):
    """Customer reference that gives a clear error for archived customers."""

    default_error_messages = {
        "does_not_exist": "Customer {pk_value} does not exist.",
        "inactive": "{name} is archived and cannot be used.",
    }

    def get_queryset(self):
        return Customer.objects.all()

    def to_internal_value(self, data):
        customer = super().to_internal_value(data)
        if not customer.is_active:
            self.fail("inactive", name=customer.full_name)
        return customer


def _validate_line_discount(product, quantity, discount, unit_price=None):
    unit_price = product.selling_price if unit_price is None else unit_price
    if discount > unit_price * quantity:
        raise serializers.ValidationError(
            {
                "discount_amount": (
                    f"Discount for {product.name} exceeds its line subtotal."
                )
            }
        )


# ---------------------------------------------------------------------------
# Read serializers
# ---------------------------------------------------------------------------


class SaleItemSerializer(serializers.ModelSerializer):
    """Sale line; cost and profit only for staff who may view cost (specs/006 R6)."""

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    line_subtotal = serializers.DecimalField(**MONEY, read_only=True)
    line_total = serializers.DecimalField(**MONEY, read_only=True)
    gross_profit = serializers.DecimalField(**MONEY, read_only=True)

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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not can_view_cost(self.context.get("request")):
            data.pop("unit_cost_price", None)
            data.pop("gross_profit", None)
        return data


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
    item_discount_total = serializers.DecimalField(**MONEY, read_only=True)
    amount_paid = serializers.DecimalField(**MONEY, read_only=True)
    balance = serializers.DecimalField(**MONEY, read_only=True)
    refund_due = serializers.DecimalField(**MONEY, read_only=True)
    items_summary = serializers.SerializerMethodField()
    payment_methods = serializers.SerializerMethodField()

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
            "item_discount_total",
            "discount_amount",
            "total_amount",
            "amount_paid",
            "balance",
            "refund_due",
            "status",
            "created_at",
            "finalized_at",
            "cancelled_at",
            "sale_date",
            "items_summary",
            "payment_methods",
        ]
        read_only_fields = fields

    def get_items_summary(self, sale) -> str:
        """e.g. "BG66 Ultimax ×1, Super Grap ×2" (uses prefetched items)."""
        return ", ".join(
            f"{item.product.name} ×{item.quantity}" for item in sale.items.all()
        )

    def get_payment_methods(self, sale) -> list[str]:
        """Distinct methods of posted receipts, in the order received."""
        methods = []
        for payment in sorted(sale.payments.all(), key=lambda p: (p.created_at, p.pk)):
            if (
                payment.payment_type == Payment.PaymentType.RECEIPT
                and payment.status == Payment.Status.POSTED
                and payment.payment_method not in methods
            ):
                methods.append(payment.payment_method)
        return methods


class SaleEventSerializer(serializers.ModelSerializer):
    performed_by = EventUserSerializer(read_only=True)

    class Meta:
        model = SaleEvent
        fields = ["id", "action", "changes", "reason", "performed_by", "created_at"]
        read_only_fields = fields


class SaleDetailSerializer(SaleListSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    events = SaleEventSerializer(many=True, read_only=True)

    class Meta(SaleListSerializer.Meta):
        fields = SaleListSerializer.Meta.fields + [
            "items",
            "payments",
            "cancellation_reason",
            "cancelled_by",
            "updated_at",
            "events",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Draft sale write serializers
#
# These are plain Serializers: only the declared input fields are accepted.
# Prices, costs, totals, status, and audit fields are never read from the
# request; the services compute or snapshot them.
# ---------------------------------------------------------------------------


class SaleItemCreateSerializer(serializers.Serializer):
    product_id = ActiveProductField(source="product")
    quantity = serializers.IntegerField(min_value=1)
    discount_amount = serializers.DecimalField(
        **LINE_MONEY,
        min_value=ZERO,
        required=False,
        default=ZERO,
    )

    def validate(self, attrs):
        _validate_line_discount(
            attrs["product"], attrs["quantity"], attrs["discount_amount"]
        )
        return attrs


class SaleCreateSerializer(serializers.Serializer):
    customer_id = ActiveCustomerField(
        source="customer",
        required=False,
        allow_null=True,
    )
    discount_amount = serializers.DecimalField(
        **MONEY,
        min_value=ZERO,
        required=False,
        default=ZERO,
    )
    items = SaleItemCreateSerializer(many=True)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("A sale must contain at least one item.")

        product_ids = [item["product"].pk for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Each product should only appear once. "
                "Combine quantities for duplicate products."
            )

        return items

    def validate(self, attrs):
        remaining = sum(
            (
                item["product"].selling_price * item["quantity"]
                - item["discount_amount"]
                for item in attrs["items"]
            ),
            ZERO,
        )

        if attrs["discount_amount"] > remaining:
            raise serializers.ValidationError(
                {"discount_amount": "Sale discount exceeds the remaining sale amount."}
            )

        return attrs

    def create(self, validated_data):
        from sales.services import create_draft_sale

        return create_draft_sale(
            user=self.context["request"].user,
            **validated_data,
        )


class SaleUpdateSerializer(serializers.Serializer):
    """Partial update of a draft sale's customer and sale-level discount."""

    customer_id = ActiveCustomerField(
        source="customer",
        required=False,
        allow_null=True,
    )
    discount_amount = serializers.DecimalField(
        **MONEY,
        min_value=ZERO,
        required=False,
    )

    def update(self, instance, validated_data):
        from sales.services import update_draft_sale

        return update_draft_sale(sale_id=instance.pk, **validated_data)


class SaleItemAddSerializer(SaleItemCreateSerializer):
    """
    Adds a product to a draft sale. If the product is already on the sale,
    the quantity and discount are merged into that line.
    """

    def validate(self, attrs):
        sale = self.context["sale"]
        existing = sale.items.filter(product=attrs["product"]).first()

        if existing is None:
            return super().validate(attrs)

        _validate_line_discount(
            attrs["product"],
            existing.quantity + attrs["quantity"],
            existing.discount_amount + attrs["discount_amount"],
            unit_price=existing.unit_selling_price,
        )
        return attrs

    def create(self, validated_data):
        from sales.services import add_sale_item

        return add_sale_item(sale_id=self.context["sale"].pk, **validated_data)


class SaleItemUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, required=False)
    discount_amount = serializers.DecimalField(
        **LINE_MONEY,
        min_value=ZERO,
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Provide a quantity and/or discount_amount."
            )

        item = self.instance
        _validate_line_discount(
            item.product,
            attrs.get("quantity", item.quantity),
            attrs.get("discount_amount", item.discount_amount),
            unit_price=item.unit_selling_price,
        )
        return attrs

    def update(self, instance, validated_data):
        from sales.services import update_sale_item

        return update_sale_item(
            sale_id=instance.sale_id,
            item_id=instance.pk,
            **validated_data,
        )


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


class PaymentCreateSerializer(serializers.Serializer):
    """
    Records a receipt or a refund. Refunds require ``notes`` as the reason.
    Status, received_by, and payment_date are set by the server.
    """

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

    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices)
    payment_type = serializers.ChoiceField(
        choices=Payment.PaymentType.choices,
        default=Payment.PaymentType.RECEIPT,
    )
    reference_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

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

        if (
            attrs["payment_type"] == Payment.PaymentType.REFUND
            and not attrs["notes"].strip()
        ):
            raise serializers.ValidationError(
                {"notes": "A reason is required for refunds."}
            )

        return attrs

    def create(self, validated_data):
        from sales.services import process_refund, record_payment

        user = self.context["request"].user

        if validated_data["payment_type"] == Payment.PaymentType.REFUND:
            validated_data.pop("payment_type")
            return process_refund(
                user=user,
                reason=validated_data.pop("notes"),
                **validated_data,
            )

        return record_payment(user=user, **validated_data)


class CartLineSerializer(serializers.Serializer):
    product_id = ActiveProductField(source="product")
    quantity = serializers.IntegerField(min_value=1)
    # Kept so completing a draft never silently drops an existing line discount.
    discount_amount = serializers.DecimalField(
        **LINE_MONEY, min_value=ZERO, required=False, default=ZERO
    )


class DraftCartSerializer(serializers.Serializer):
    """Body of PUT /api/sales/{id}/draft/ and the cart part of checkout."""

    customer_id = ActiveCustomerField(
        source="customer", required=False, allow_null=True
    )
    items = CartLineSerializer(many=True)
    discount_amount = serializers.DecimalField(
        **MONEY, min_value=ZERO, required=False, default=ZERO
    )


class CheckoutPaymentSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices)
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    reference_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )


class CheckoutSerializer(DraftCartSerializer):
    """Body of POST /api/sales/checkout/ (contracts/sales-api.md)."""

    client_transaction_id = serializers.UUIDField(required=False, allow_null=True)
    draft_id = serializers.IntegerField(required=False, allow_null=True)
    sale_date = serializers.DateField(required=False, allow_null=True)
    backdate_reason = serializers.CharField(
        required=False, allow_blank=True, default="", trim_whitespace=False
    )
    payment = CheckoutPaymentSerializer(required=False, allow_null=True)


class SaleCustomerChangeSerializer(serializers.Serializer):
    customer_id = ActiveCustomerField(source="customer")
    reason = serializers.CharField(allow_blank=True)
