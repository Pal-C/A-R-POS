"""API endpoint handlers"""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Product, ProductEvent
from .serializers import (
    ProductDetailSerializer,
    ProductEventSerializer,
    ProductSerializer,
    ProductUpdateSerializer,
    ProductWriteSerializer,
    ReasonSerializer,
    can_view_cost,
)
from .services import (
    ProductConflict,
    create_product,
    deactivate_product,
    reactivate_product,
    update_product,
)


class CostAwareOrderingFilter(filters.OrderingFilter):
    """Ignores ordering by cost for users who may not see cost (research R8)."""

    def get_valid_fields(self, queryset, view, context=None):
        fields = super().get_valid_fields(queryset, view, context or {})
        request = (context or {}).get("request") or getattr(view, "request", None)
        if can_view_cost(request):
            return fields
        return [(name, label) for name, label in fields if name != "cost_price"]


def run_service(func, *args, **kwargs):
    """Calls a service, converting Django validation errors to HTTP 400."""
    try:
        return func(*args, **kwargs)
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        raise ValidationError(detail) from None


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [
        filters.SearchFilter,
        CostAwareOrderingFilter,
    ]

    search_fields = [
        "sku",
        "name",
        "brand",
        "subcategory",
        "category",
    ]

    ordering_fields = [
        "name",
        "sku",
        "category",
        "selling_price",
        "cost_price",
        "stock_quantity",
        "created_at",
    ]

    ordering = ["name"]

    def get_queryset(self):
        queryset = Product.objects.all()
        params = self.request.query_params

        category = params.get("category")
        subcategory = params.get("subcategory")
        is_active = params.get("is_active")
        min_price = params.get("min_price")
        max_price = params.get("max_price")
        stock_status = params.get("stock_status")

        if category:
            queryset = queryset.filter(category=category.upper())

        if subcategory:
            queryset = queryset.filter(subcategory__iexact=subcategory)

        if is_active is not None:
            if is_active.lower() == "true":
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() == "false":
                queryset = queryset.filter(is_active=False)
            else:
                raise ValidationError({"is_active": "Use true or false."})

        for parameter, value, lookup in [
            ("min_price", min_price, "gte"),
            ("max_price", max_price, "lte"),
        ]:
            if value is not None:
                try:
                    price = Decimal(value)

                    if not price.is_finite() or price < 0:
                        raise ValueError

                except (InvalidOperation, ValueError):
                    raise ValidationError(
                        {parameter: "Enter a valid nonnegative price."}
                    ) from None

                queryset = queryset.filter(**{f"selling_price__{lookup}": price})

        if min_price is not None and max_price is not None:
            if Decimal(min_price) > Decimal(max_price):
                raise ValidationError(
                    {"price": "Minimum price cannot exceed maximum price."}
                )

        if stock_status:
            stock_status = stock_status.upper()

            if stock_status == "OUT_OF_STOCK":
                queryset = queryset.filter(stock_quantity=0)

            elif stock_status == "LOW_STOCK":
                queryset = queryset.filter(
                    stock_quantity__gt=0,
                    stock_quantity__lte=F("low_stock_threshold"),
                )

            elif stock_status == "IN_STOCK":
                queryset = queryset.filter(stock_quantity__gt=F("low_stock_threshold"))

            else:
                raise ValidationError(
                    {"stock_status": ("Use IN_STOCK, LOW_STOCK, or OUT_OF_STOCK.")}
                )

        return queryset

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "Products cannot be permanently deleted. "
                    "Use the deactivate action instead."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def retrieve(self, request, *args, **kwargs):
        latest = ProductEvent.objects.select_related("performed_by").order_by(
            "-created_at", "-id"
        )
        product = get_object_or_404(
            Product.objects.prefetch_related(
                Prefetch("events", queryset=latest[:1], to_attr="latest_events")
            ),
            pk=kwargs["pk"],
        )
        return Response(
            ProductDetailSerializer(product, context={"request": request}).data
        )

    def create(self, request, *args, **kwargs):
        serializer = ProductWriteSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        initial_stock = data.pop("initial_stock", 0)
        product = run_service(
            create_product, user=request.user, data=data, initial_stock=initial_stock
        )
        return Response(
            ProductSerializer(product, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use PATCH with changes, expected and reason."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        instance = get_object_or_404(Product, pk=kwargs["pk"])
        serializer = ProductUpdateSerializer(
            instance, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        try:
            run_service(
                update_product,
                product_id=instance.pk,
                user=request.user,
                changes=serializer.validated_data["changes"],
                expected=serializer.validated_data["expected"],
                reason=serializer.validated_data["reason"],
            )
        except ProductConflict as conflict:
            return Response(
                {"detail": str(conflict), "current": conflict.current},
                status=status.HTTP_409_CONFLICT,
            )
        return self.retrieve(request, pk=instance.pk)

    def _state_change(self, request, pk, service, message):
        get_object_or_404(Product, pk=pk)
        body = ReasonSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        product = run_service(
            service,
            product_id=pk,
            user=request.user,
            reason=body.validated_data["reason"],
        )
        return Response(
            {
                "detail": message,
                "product": ProductSerializer(
                    product, context={"request": request}
                ).data,
            }
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        return self._state_change(
            request, pk, deactivate_product, "Product deactivated successfully."
        )

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        return self._state_change(
            request, pk, reactivate_product, "Product reactivated successfully."
        )

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        get_object_or_404(Product, pk=pk)
        events = ProductEvent.objects.filter(product_id=pk).select_related(
            "performed_by"
        )
        page = self.paginate_queryset(events)
        serializer = ProductEventSerializer(
            page, many=True, context={"request": request}
        )
        return self.get_paginated_response(serializer.data)
