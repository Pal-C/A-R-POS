from decimal import Decimal

from rest_framework import serializers

from catalog.models import Product
from customers.models import Customer
from preorders.models import PreOrder
from sales.models import Payment

ZERO = Decimal("0.00")
ORDER_MONEY = {"max_digits": 10, "decimal_places": 2}
MONEY = {"max_digits": 12, "decimal_places": 2}


def _money(value):
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


class CustomerRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "full_name", "phone_number", "is_active"]
        read_only_fields = fields


class ProductRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "sku", "name", "is_active"]
        read_only_fields = fields


class UserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    username = serializers.CharField(source="get_username")


class PreOrderListSerializer(serializers.ModelSerializer):
    """
    Pre-order representation from the contract. Expects a queryset from
    ``preorders.selectors.preorder_queryset`` (``order_total``,
    ``amount_paid``, ``payment_state``, ``is_overdue`` annotations).
    """

    customer = CustomerRefSerializer(read_only=True)
    product = ProductRefSerializer(read_only=True)
    created_by = UserRefSerializer(read_only=True)
    fulfilled_by = UserRefSerializer(read_only=True, allow_null=True)
    cancelled_by = UserRefSerializer(read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display")
    total_amount = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    refund_due = serializers.SerializerMethodField()
    payment_state = serializers.CharField()
    is_overdue = serializers.BooleanField()

    class Meta:
        model = PreOrder
        fields = [
            "id",
            "order_number",
            "customer",
            "product",
            "quantity",
            "agreed_unit_price",
            "total_amount",
            "amount_paid",
            "balance",
            "refund_due",
            "payment_state",
            "expected_arrival_date",
            "is_overdue",
            "status",
            "status_display",
            "created_by",
            "created_at",
            "updated_at",
            "ordered_at",
            "arrived_at",
            "fulfilled_at",
            "fulfilled_by",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
        ]
        read_only_fields = fields

    def _is_cancelled(self, preorder):
        return preorder.status == PreOrder.Status.CANCELLED

    def get_total_amount(self, preorder):
        return _money(preorder.order_total)

    def get_amount_paid(self, preorder):
        return _money(preorder.amount_paid)

    def get_balance(self, preorder):
        # Cancelled pre-orders owe nothing; settled ones stay at zero.
        if self._is_cancelled(preorder) or preorder.is_settled:
            return _money(ZERO)
        return _money(max(preorder.order_total - preorder.amount_paid, ZERO))

    def get_refund_due(self, preorder):
        if self._is_cancelled(preorder):
            return _money(max(preorder.amount_paid, ZERO))
        return _money(ZERO)


class PreOrderDetailSerializer(PreOrderListSerializer):
    class Meta(PreOrderListSerializer.Meta):
        fields = [*PreOrderListSerializer.Meta.fields, "notes"]
        read_only_fields = fields


class PreOrderPaymentSerializer(serializers.ModelSerializer):
    received_by = UserRefSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "payment_method",
            "payment_type",
            "status",
            "payment_date",
            "reference_number",
            "notes",
            "received_by",
        ]
        read_only_fields = fields


class ProductSummarySerializer(serializers.Serializer):
    product = ProductRefSerializer()
    waiting = serializers.DictField()
    ordered_preorders = PreOrderListSerializer(many=True)


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


class PreOrderCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    agreed_unit_price = serializers.DecimalField(
        **ORDER_MONEY, min_value=ZERO, required=False
    )
    expected_arrival_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class PreOrderUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, required=False)
    agreed_unit_price = serializers.DecimalField(
        **ORDER_MONEY, min_value=ZERO, required=False
    )
    expected_arrival_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=PreOrder.Status.choices)
    expected_status = serializers.ChoiceField(
        choices=PreOrder.Status.choices, required=False
    )


class ArrivalSerializer(serializers.Serializer):
    received_quantity = serializers.IntegerField(min_value=1)
    preorder_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=False
    )


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField()


class PreOrderPaymentCreateSerializer(serializers.Serializer):
    payment_type = serializers.ChoiceField(
        choices=Payment.PaymentType.choices, default=Payment.PaymentType.RECEIPT
    )
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices)
    reference_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if (
            attrs["payment_type"] == Payment.PaymentType.REFUND
            and not attrs["reason"].strip()
        ):
            raise serializers.ValidationError(
                {"reason": ["A reason is required for refunds."]}
            )
        return attrs
