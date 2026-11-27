"""Validate incoming data and format API responses"""

from rest_framework import serializers

from .models import Product, ProductEvent

VIEW_COST_PERMISSION = "catalog.view_product_cost"


def can_view_cost(request) -> bool:
    """Whether the requesting user may see product cost (constitution)."""
    user = getattr(request, "user", None)
    return bool(user and user.has_perm(VIEW_COST_PERMISSION))


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
            "model",
            "supplier",
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not can_view_cost(self.context.get("request")):
            data.pop("cost_price", None)
        return data

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
            raise serializers.ValidationError("A product with this SKU already exists.")

        return value

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Product name cannot be empty.")

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
            raise serializers.ValidationError(
                {"selling_price": "Selling price cannot be negative."}
            )

        if cost_price is not None and cost_price < 0:
            raise serializers.ValidationError(
                {"cost_price": "Cost price cannot be negative."}
            )

        return attrs


class ReasonSerializer(serializers.Serializer):
    """Body of deactivate/reactivate; the service rejects a blank reason."""

    reason = serializers.CharField(allow_blank=True, required=False, default="")


class ProductWriteSerializer(ProductSerializer):
    """Create/edit input: writable product fields plus the optional starting stock."""

    initial_stock = serializers.IntegerField(
        required=False, min_value=0, write_only=True, default=0
    )

    class Meta(ProductSerializer.Meta):
        fields = [*ProductSerializer.Meta.fields, "initial_stock"]
        extra_kwargs = {"cost_price": {"required": False}}


class ProductUpdateSerializer(serializers.Serializer):
    """Audited edit: ``changes`` with the ``expected`` original values and a reason."""

    changes = serializers.DictField()
    expected = serializers.DictField()
    reason = serializers.CharField(allow_blank=True, trim_whitespace=False)

    def validate(self, attrs):
        changes = dict(attrs["changes"])
        from .services import EDITABLE_FIELDS

        unknown = sorted(set(changes) - set(EDITABLE_FIELDS))
        if unknown:
            raise serializers.ValidationError(
                {"changes": f"These fields cannot be edited: {', '.join(unknown)}."}
            )

        validated = {}
        if "stock_quantity" in changes:
            stock = serializers.IntegerField(min_value=0)
            try:
                validated["stock_quantity"] = stock.run_validation(
                    changes.pop("stock_quantity")
                )
            except serializers.ValidationError as exc:
                raise serializers.ValidationError(
                    {"stock_quantity": exc.detail}
                ) from None
        if changes:
            fields = ProductWriteSerializer(
                instance=self.instance, data=changes, partial=True, context=self.context
            )
            fields.is_valid(raise_exception=True)
            validated.update(
                {k: v for k, v in fields.validated_data.items() if k in changes}
            )
        attrs["changes"] = validated
        return attrs


class EventUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, user) -> str:
        return user.get_full_name() or user.username


class ProductEventSerializer(serializers.ModelSerializer):
    performed_by = EventUserSerializer(read_only=True)

    class Meta:
        model = ProductEvent
        fields = ["id", "action", "changes", "reason", "performed_by", "created_at"]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not can_view_cost(self.context.get("request")):
            data["changes"] = {
                k: v for k, v in data["changes"].items() if k != "cost_price"
            }
        return data


class ProductDetailSerializer(ProductSerializer):
    """Detail view: adds the most recent history entry ("Last updated … by …")."""

    last_event = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = [*ProductSerializer.Meta.fields, "last_event"]

    def get_last_event(self, product):
        events = getattr(product, "latest_events", None)
        if events is None:
            events = list(
                product.events.select_related("performed_by").order_by(
                    "-created_at", "-id"
                )[:1]
            )
        if not events:
            return None
        event = events[0]
        return {
            "action": event.action,
            "performed_by": EventUserSerializer(event.performed_by).data,
            "created_at": serializers.DateTimeField().to_representation(
                event.created_at
            ),
        }
