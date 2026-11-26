"""Thin DRF views for pre-orders (contracts/preorders-api.md)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from preorders.models import PreOrder
from preorders.selectors import (
    preorder_history,
    preorder_queryset,
    product_preorder_summary,
    search_preorders,
)
from preorders.serializers import (
    ArrivalSerializer,
    CancelSerializer,
    PreOrderCreateSerializer,
    PreOrderDetailSerializer,
    PreOrderListSerializer,
    PreOrderPaymentCreateSerializer,
    PreOrderPaymentSerializer,
    PreOrderUpdateSerializer,
    ProductSummarySerializer,
    StatusChangeSerializer,
)
from preorders.services import (
    StatusConflict,
    cancel_preorder,
    change_status,
    create_preorder,
    fulfill_preorder,
    mark_product_arrived,
    record_preorder_payment,
    update_preorder,
)
from sales.models import Payment

CANCEL_PERMISSION = "preorders.cancel_preorder"
OVERRIDE_PRICE_PERMISSION = "preorders.override_preorder_price"
RECORD_PAYMENT_PERMISSION = "sales.record_payment"
REFUND_PERMISSION = "sales.process_refund"


def run_service(func, *args, **kwargs):
    """Calls a service or selector, converting Django validation errors to HTTP 400."""
    try:
        return func(*args, **kwargs)
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        raise ValidationError(detail) from None


def get_preorder(pk):
    return get_object_or_404(PreOrder, pk=pk)


def detail_data(pk):
    return PreOrderDetailSerializer(get_object_or_404(preorder_queryset(), pk=pk)).data


def detail_response(pk, status_code=status.HTTP_200_OK):
    return Response(detail_data(pk), status=status_code)


class PreOrderListCreateView(generics.ListCreateAPIView):
    """GET: paged search and filters (FR-018–020). POST: create (FR-001–004)."""

    permission_classes = [IsAuthenticated]
    serializer_class = PreOrderListSerializer
    filter_backends = []

    def get_queryset(self):
        return run_service(search_preorders, self.request.query_params)

    def create(self, request, *args, **kwargs):
        serializer = PreOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preorder = run_service(
            create_preorder, user=request.user, **serializer.validated_data
        )
        return detail_response(preorder.pk, status.HTTP_201_CREATED)


class PreOrderDetailView(APIView):
    """GET: details. PATCH: edit (FR-005). No DELETE (FR-024)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        return detail_response(pk)

    def patch(self, request, pk):
        get_preorder(pk)
        serializer = PreOrderUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # A price override without permission raises Django's
        # PermissionDenied, which DRF returns as 403.
        run_service(
            update_preorder,
            preorder_id=pk,
            user=request.user,
            can_override_price=request.user.has_perm(OVERRIDE_PRICE_PERMISSION),
            **serializer.validated_data,
        )
        return detail_response(pk)


class PreOrderStatusView(APIView):
    """POST: single-step status change (FR-007–008)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        get_preorder(pk)
        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            change_status(
                preorder_id=pk,
                user=request.user,
                to_status=serializer.validated_data["status"],
                expected_status=serializer.validated_data.get("expected_status"),
            )
        except StatusConflict as exc:
            return Response(
                {"detail": exc.messages[0], "current_status": exc.current_status},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from None
        return detail_response(pk)


class PreOrderFulfillView(APIView):
    """POST: hand over an arrived, fully paid pre-order (FR-016)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        get_preorder(pk)
        run_service(fulfill_preorder, preorder_id=pk, user=request.user)
        return detail_response(pk)


class PreOrderCancelView(APIView):
    """POST: cancel with a reason (FR-022–023)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.has_perm(CANCEL_PERMISSION):
            raise PermissionDenied("You do not have permission to cancel pre-orders.")
        get_preorder(pk)
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_service(
            cancel_preorder,
            preorder_id=pk,
            user=request.user,
            reason=serializer.validated_data["reason"],
        )
        return detail_response(pk)


class PreOrderPaymentsView(generics.ListAPIView):
    """GET: the pre-order's payments, newest first. POST: receipt or refund."""

    permission_classes = [IsAuthenticated]
    serializer_class = PreOrderPaymentSerializer
    filter_backends = []

    def get_queryset(self):
        preorder = get_preorder(self.kwargs["pk"])
        return (
            Payment.objects.filter(preorder=preorder)
            .select_related("received_by")
            .order_by("-payment_date", "-id")
        )

    def post(self, request, pk):
        serializer = PreOrderPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data["payment_type"] == Payment.PaymentType.REFUND:
            if not request.user.has_perm(REFUND_PERMISSION):
                raise PermissionDenied("You do not have permission to process refunds.")
        elif not request.user.has_perm(RECORD_PAYMENT_PERMISSION):
            raise PermissionDenied("You do not have permission to record payments.")

        get_preorder(pk)
        payment, _ = run_service(
            record_preorder_payment, preorder_id=pk, user=request.user, **data
        )
        return Response(
            {
                "payment": PreOrderPaymentSerializer(payment).data,
                "preorder": detail_data(pk),
            },
            status=status.HTTP_201_CREATED,
        )


class PreOrderHistoryView(APIView):
    """GET: audit history, oldest first (FR-025)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        return Response(preorder_history(get_preorder(pk)))


class ProductPreorderSummaryView(APIView):
    """GET: units waiting per status and the product's Ordered pre-orders (FR-021)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        summary = product_preorder_summary(product)
        return Response(ProductSummarySerializer(summary).data)


class ProductArrivalView(APIView):
    """POST: mark a product as arrived (FR-009)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, product_id):
        get_object_or_404(Product, pk=product_id)
        serializer = ArrivalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = run_service(
            mark_product_arrived,
            product_id=product_id,
            user=request.user,
            received_quantity=serializer.validated_data["received_quantity"],
            preorder_ids=serializer.validated_data.get("preorder_ids"),
        )
        marked = preorder_queryset().filter(
            pk__in=[order.pk for order in result["marked"]]
        )
        return Response(
            {
                "marked": PreOrderListSerializer(
                    marked.order_by("created_at", "id"), many=True
                ).data,
                "units_used": result["units_used"],
                "units_left": result["units_left"],
            }
        )
