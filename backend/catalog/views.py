"""	API endpoint handlers """
from decimal import Decimal, InvalidOperation

from django.db.models import F

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Product
from .serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
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
            queryset = queryset.filter(
                subcategory__iexact=subcategory
            )

        if is_active is not None:
            if is_active.lower() == "true":
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() == "false":
                queryset = queryset.filter(is_active=False)
            else:
                raise ValidationError({
                    "is_active": "Use true or false."
                })

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
                    raise ValidationError({
                        parameter: "Enter a valid nonnegative price."
                    })

                queryset = queryset.filter(
                    **{f"selling_price__{lookup}": price}
                )

        if min_price is not None and max_price is not None:
            if Decimal(min_price) > Decimal(max_price):
                raise ValidationError({
                    "price": "Minimum price cannot exceed maximum price."
                })

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
                queryset = queryset.filter(
                    stock_quantity__gt=F("low_stock_threshold")
                )

            else:
                raise ValidationError({
                    "stock_status": (
                        "Use IN_STOCK, LOW_STOCK, or OUT_OF_STOCK."
                    )
                })

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

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        product = self.get_object()

        if not product.is_active:
            return Response(
                {"detail": "Product is already inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])

        return Response({
            "detail": "Product deactivated successfully.",
            "product": self.get_serializer(product).data,
        })

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        product = self.get_object()

        if product.is_active:
            return Response(
                {"detail": "Product is already active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product.is_active = True
        product.save(update_fields=["is_active", "updated_at"])

        return Response({
            "detail": "Product reactivated successfully.",
            "product": self.get_serializer(product).data,
        })
