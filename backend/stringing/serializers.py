from decimal import Decimal

from rest_framework import serializers

from customers.models import Customer
from sales.models import Payment
from stringing.models import StringingOrder

FINANCIALS_PERMISSION = "stringing.view_stringing_financials"
FINANCIAL_FIELDS = ("direct_cost", "profit")

ZERO = Decimal("0.00")
ORDER_MONEY = {"max_digits": 10, "decimal_places": 2}
MONEY = {"max_digits": 12, "decimal_places": 2}


def can_view_financials(user):
    return bool(user and user.has_perm(FINANCIALS_PERMISSION))


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


class UserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    username = serializers.CharField(source="get_username")


class StringingOrderListSerializer(serializers.ModelSerializer):
    """
    Order representation from the contract. Expects a queryset from
    ``stringing.selectors.order_queryset`` (``order_total``,
    ``amount_paid``, ``payment_state`` annotations). Direct cost and
    profit are omitted unless the user has the financials permission.
    """

    customer = CustomerRefSerializer(read_only=True)
    created_by = UserRefSerializer(read_only=True)
    cancelled_by = UserRefSerializer(read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display")
    add_ons_total = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    profit = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    refund_due = serializers.SerializerMethodField()
    payment_state = serializers.CharField()

    class Meta:
        model = StringingOrder
        fields = [
            "id",
            "order_number",
            "customer",
            "racket_description",
            "string_type",
            "string_color",
            "tension",
            "service_price",
            "string_from_store",
            "has_stencil",
            "stencil_price",
            "has_grip",
            "grip_price",
            "add_ons_total",
            "discount_amount",
            "total_amount",
            "direct_cost",
            "profit",
            "amount_paid",
            "balance",
            "refund_due",
            "payment_state",
            "status",
            "status_display",
            "created_by",
            "created_at",
            "updated_at",
            "ready_at",
            "completed_at",
            "paid_in_full_at",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "materials_used",
        ]
        read_only_fields = fields

    def _is_cancelled(self, order):
        return order.status == StringingOrder.Status.CANCELLED

    def get_add_ons_total(self, order):
        return _money(order.add_ons_total)

    def get_total_amount(self, order):
        return _money(order.order_total)

    def get_profit(self, order):
        return _money(order.order_total - order.direct_cost)

    def get_amount_paid(self, order):
        return _money(order.amount_paid)

    def get_balance(self, order):
        # Cancelled orders owe nothing; settled orders stay at zero even
        # after a refund made after pickup (FR-028).
        if self._is_cancelled(order) or order.is_settled:
            return _money(ZERO)
        return _money(max(order.order_total - order.amount_paid, ZERO))

    def get_refund_due(self, order):
        if self._is_cancelled(order):
            return _money(max(order.amount_paid, ZERO))
        return _money(ZERO)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if not can_view_financials(getattr(request, "user", None)):
            for field in FINANCIAL_FIELDS:
                data.pop(field, None)
        return data


class StringingOrderDetailSerializer(StringingOrderListSerializer):
    class Meta(StringingOrderListSerializer.Meta):
        fields = [*StringingOrderListSerializer.Meta.fields, "notes"]
        read_only_fields = fields


class OrderPaymentSerializer(serializers.ModelSerializer):
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


class RevenueReportSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    orders_count = serializers.IntegerField()
    gross_service_price = serializers.DecimalField(**MONEY)
    gross_add_ons = serializers.DecimalField(**MONEY)
    total_discounts = serializers.DecimalField(**MONEY)
    net_revenue = serializers.DecimalField(**MONEY)
    total_direct_cost = serializers.DecimalField(**MONEY)
    profit = serializers.DecimalField(**MONEY)
    total_refunds = serializers.DecimalField(**MONEY)
    net_revenue_after_refunds = serializers.DecimalField(**MONEY)
    profit_after_refunds = serializers.DecimalField(**MONEY)
    cancelled_count = serializers.IntegerField()
    unpaid_count = serializers.IntegerField()
    outstanding_balance = serializers.DecimalField(**MONEY)


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


class StringingOrderWriteSerializer(serializers.Serializer):
    """Create (all required fields) or partial update input."""

    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True
    )
    racket_description = serializers.CharField(max_length=150)
    string_type = serializers.CharField(max_length=150)
    string_color = serializers.CharField(
        max_length=50, required=False, allow_blank=True
    )
    tension = serializers.CharField(max_length=50, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    service_price = serializers.DecimalField(**ORDER_MONEY, min_value=ZERO)
    discount_amount = serializers.DecimalField(
        **ORDER_MONEY, min_value=ZERO, required=False
    )
    direct_cost = serializers.DecimalField(
        **ORDER_MONEY, min_value=ZERO, required=False
    )
    string_from_store = serializers.BooleanField(required=False)
    has_stencil = serializers.BooleanField(required=False)
    stencil_price = serializers.DecimalField(
        **ORDER_MONEY, min_value=ZERO, required=False
    )
    has_grip = serializers.BooleanField(required=False)
    grip_price = serializers.DecimalField(**ORDER_MONEY, min_value=ZERO, required=False)


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices)
    reference_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )


class StringingOrderCreateSerializer(StringingOrderWriteSerializer):
    """Create input: order fields plus an optional deposit (specs/007 R3)."""

    deposit = DepositSerializer(required=False, allow_null=True)
    client_transaction_id = serializers.UUIDField(required=False, allow_null=True)


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=StringingOrder.Status.choices)
    expected_status = serializers.ChoiceField(
        choices=StringingOrder.Status.choices, required=False
    )


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField()
    materials_used = serializers.BooleanField()


class OrderPaymentCreateSerializer(serializers.Serializer):
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


class RevenueReportQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()

    def validate(self, attrs):
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError(
                {"date_to": ["End date must be on or after the start date."]}
            )
        return attrs
