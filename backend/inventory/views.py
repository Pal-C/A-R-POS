from django.shortcuts import render
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from catalog.serializers import ProductSerializer

from inventory.models import InventoryMovement
from inventory.serializers import (
    InventoryMovementSerializer,
    RestockSerializer,
    StockAdjustmentSerializer,
    ReverseMovementSerializer,
)
from inventory.services import (
    restock_product,
    adjust_stock,
    reverse_movement,
)

# Create your views here.
def handle_service_validation_error(error):
    """
    Converts Django ValidationError into a DRF ValidationError
    so service-layer validation errors return HTTP 400 responses.
    """

    if hasattr(error, "message_dict"):
        detail = error.message_dict
    else:
        detail = error.messages

    raise ValidationError(detail)


class InventoryMovementListView(generics.ListAPIView):
    """
    Returns inventory movement history.

    Supported query parameters:
    - product_id
    - movement_type
    - start_date (YYYY-MM-DD)
    - end_date (YYYY-MM-DD)
    """

    serializer_class = InventoryMovementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            InventoryMovement.objects
            .select_related("product", "created_by", "sale_item")
            .all()
        )

        product_id = self.request.query_params.get("product_id")
        movement_type = self.request.query_params.get("movement_type")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if product_id:
            if not product_id.isdigit():
                raise ValidationError({
                    "product_id": "Must be a valid product ID."
                })

            queryset = queryset.filter(product_id=product_id)

        if movement_type:
            valid_types = InventoryMovement.MovementType.values

            if movement_type not in valid_types:
                raise ValidationError({
                    "movement_type": "Invalid movement type."
                })

            queryset = queryset.filter(movement_type=movement_type)

        if start_date:
            parsed_start_date = parse_date(start_date)

            if parsed_start_date is None:
                raise ValidationError({
                    "start_date": "Use the YYYY-MM-DD date format."
                })

            queryset = queryset.filter(
                movement_date__date__gte=parsed_start_date
            )

        if end_date:
            parsed_end_date = parse_date(end_date)

            if parsed_end_date is None:
                raise ValidationError({
                    "end_date": "Use the YYYY-MM-DD date format."
                })

            queryset = queryset.filter(
                movement_date__date__lte=parsed_end_date
            )

        if start_date and end_date:
            if parsed_start_date > parsed_end_date:
                raise ValidationError({
                    "date_range": "start_date cannot be later than end_date."
                })

        return queryset


class InventoryMovementDetailView(generics.RetrieveAPIView):
    """
    Returns the details of a single inventory movement.
    """

    queryset = InventoryMovement.objects.select_related(
        "product",
        "created_by",
        "sale_item"
    )
    serializer_class = InventoryMovementSerializer
    permission_classes = [IsAuthenticated]


class RestockView(APIView):
    """
    Records newly received supplier stock.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RestockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            movement = restock_product(
                product_id=data["product"].id,
                quantity_received=data["quantity_received"],
                created_by=request.user,
                reason=data["reason"],
                reference_number=data["reference_number"],
            )
        except DjangoValidationError as error:
            handle_service_validation_error(error)

        response_serializer = InventoryMovementSerializer(movement)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


class StockAdjustmentView(APIView):
    """
    Records a manual stock increase or decrease.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            movement = adjust_stock(
                product_id=data["product"].id,
                quantity_change=data["quantity_change"],
                reason=data["reason"],
                created_by=request.user,
                reference_number=data["reference_number"],
            )
        except DjangoValidationError as error:
            handle_service_validation_error(error)

        response_serializer = InventoryMovementSerializer(movement)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


class ReverseInventoryMovementView(APIView):
    """
    Reverses an existing inventory movement.

    The original movement is preserved.
    A new reversal movement is created instead.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = ReverseMovementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Check that the original movement exists.
        get_object_or_404(InventoryMovement, pk=pk)

        try:
            movement = reverse_movement(
                movement_id=pk,
                created_by=request.user,
                reason=data["reason"],
                reference_number=data["reference_number"],
            )
        except DjangoValidationError as error:
            handle_service_validation_error(error)

        response_serializer = InventoryMovementSerializer(movement)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


class LowStockProductsView(generics.ListAPIView):
    """
    Returns active products with stock below or equal to
    their low-stock threshold, excluding out-of-stock products.
    """

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True,
            stock_quantity__gt=0,
            stock_quantity__lte=F("low_stock_threshold")
        ).order_by("stock_quantity", "name")


class OutOfStockProductsView(generics.ListAPIView):
    """
    Returns active products with zero stock.
    """

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True,
            stock_quantity=0
        ).order_by("name")


class InventorySummaryView(APIView):
    """
    Returns high-level inventory statistics.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        products = Product.objects.filter(is_active=True)

        low_stock_products = products.filter(
            stock_quantity__gt=0,
            stock_quantity__lte=F("low_stock_threshold")
        )

        out_of_stock_products = products.filter(
            stock_quantity=0
        )

        summary = {
            "active_product_count": products.count(),
            "total_units_in_stock": (
                products.aggregate(
                    total=Sum("stock_quantity")
                )["total"] or 0
            ),
            "low_stock_count": low_stock_products.count(),
            "out_of_stock_count": out_of_stock_products.count(),
        }

        return Response(summary, status=status.HTTP_200_OK)
