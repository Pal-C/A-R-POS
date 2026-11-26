from rest_framework import serializers

from customers.models import Customer, CustomerAuditEvent
from preorders.models import PreOrder
from sales.models import Sale
from stringing.models import StringingOrder

MONEY = {"max_digits": 14, "decimal_places": 2, "read_only": True}


class CustomerSummarySerializer(serializers.Serializer):
    """Read-only shape of customers.selectors.customer_summary()."""

    sales_count = serializers.IntegerField(read_only=True)
    stringing_orders_count = serializers.IntegerField(read_only=True)
    preorders_count = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(**MONEY)
    outstanding_balance = serializers.DecimalField(**MONEY)
    open_preorders_count = serializers.IntegerField(read_only=True)
    unfinished_stringing_orders_count = serializers.IntegerField(read_only=True)


class CustomerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "full_name", "phone_number", "email", "is_active"]
        read_only_fields = fields


class ArchiveEventSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(
        source="performed_by.username", read_only=True
    )

    class Meta:
        model = CustomerAuditEvent
        fields = ["action", "performed_by", "performed_by_name", "created_at"]
        read_only_fields = fields


class CustomerDetailSerializer(serializers.ModelSerializer):
    """
    Customer details plus the history summary and the latest archive or
    reactivate event (FR-009, FR-013, FR-021).
    """

    summary = serializers.SerializerMethodField()
    last_archive_event = serializers.SerializerMethodField()

    def get_last_archive_event(self, customer):
        from customers.selectors import last_archive_event

        event = last_archive_event(customer)
        return ArchiveEventSerializer(event).data if event else None

    def get_summary(self, customer):
        from customers.selectors import customer_summary

        return CustomerSummarySerializer(customer_summary(customer)).data

    class Meta:
        model = Customer
        fields = [
            "id",
            "full_name",
            "phone_number",
            "email",
            "address",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
            "last_archive_event",
            "summary",
        ]
        read_only_fields = fields


class CustomerWriteSerializer(serializers.Serializer):
    """
    Input for creating and editing customers. Only the editable fields are
    accepted; anything else in the request body is ignored. The field rules
    (data-model.md Customer.full_name, Customer.phone_number,
    Customer.email) are enforced by customers.services so they apply to
    every caller.
    """

    full_name = serializers.CharField(allow_blank=True, trim_whitespace=False)
    phone_number = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    email = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        from customers.services import create_customer

        return create_customer(**validated_data)

    def update(self, instance, validated_data):
        from customers.services import update_customer

        return update_customer(instance.pk, **validated_data)


# ---------------------------------------------------------------------------
# History rows (read-only; querysets come from customers.selectors)
# ---------------------------------------------------------------------------


class CustomerSaleHistorySerializer(serializers.ModelSerializer):
    amount_paid = serializers.DecimalField(source="net_paid", **MONEY)
    balance = serializers.DecimalField(source="outstanding", **MONEY)

    class Meta:
        model = Sale
        fields = [
            "id",
            "sale_number",
            "finalized_at",
            "status",
            "total_amount",
            "amount_paid",
            "balance",
        ]
        read_only_fields = fields


class CustomerStringingHistorySerializer(serializers.ModelSerializer):
    total_amount = serializers.DecimalField(source="order_total", **MONEY)

    class Meta:
        model = StringingOrder
        fields = [
            "id",
            "order_number",
            "racket_description",
            "string_type",
            "tension",
            "status",
            "total_amount",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields


class CustomerPreorderHistorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    total_amount = serializers.DecimalField(source="order_total", **MONEY)
    amount_paid = serializers.DecimalField(source="net_paid", **MONEY)

    class Meta:
        model = PreOrder
        fields = [
            "id",
            "order_number",
            "product",
            "product_name",
            "product_sku",
            "quantity",
            "total_amount",
            "expected_arrival_date",
            "status",
            "amount_paid",
            "created_at",
        ]
        read_only_fields = fields
