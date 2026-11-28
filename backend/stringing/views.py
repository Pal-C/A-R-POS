"""Thin DRF views for stringing orders (contracts/stringing-api.md)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sales.models import Payment
from stringing.models import StringingOrder
from stringing.selectors import (
    order_history,
    order_queryset,
    revenue_report,
    search_orders,
    status_counts,
)
from stringing.serializers import (
    CancelSerializer,
    OrderPaymentCreateSerializer,
    OrderPaymentSerializer,
    RevenueReportQuerySerializer,
    RevenueReportSerializer,
    StatusChangeSerializer,
    StringingOrderCreateSerializer,
    StringingOrderDetailSerializer,
    StringingOrderListSerializer,
    StringingOrderWriteSerializer,
    can_view_financials,
)
from stringing.services import (
    StatusConflict,
    cancel_stringing_order,
    change_status,
    record_order_payment,
    take_in_order,
    update_stringing_order,
)

CANCEL_PERMISSION = "stringing.cancel_stringingorder"
RECORD_PAYMENT_PERMISSION = "sales.record_payment"
REFUND_PERMISSION = "sales.process_refund"


def run_service(func, *args, **kwargs):
    """Calls a service or selector, converting Django validation errors to HTTP 400."""
    try:
        return func(*args, **kwargs)
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        raise ValidationError(detail) from None


def get_order(pk):
    return get_object_or_404(StringingOrder, pk=pk)


def detail_response(request, pk, status_code=status.HTTP_200_OK):
    order = get_object_or_404(order_queryset(), pk=pk)
    data = StringingOrderDetailSerializer(order, context={"request": request}).data
    return Response(data, status=status_code)


class StringingOrderListCreateView(generics.ListCreateAPIView):
    """
    GET: paged search and filters (FR-018–020). POST: create with an
    optional deposit, idempotent by ``client_transaction_id`` (201 new,
    200 repeat; specs/007 R3).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = StringingOrderListSerializer
    filter_backends = []

    def get_queryset(self):
        return run_service(search_orders, self.request.query_params)

    def create(self, request, *args, **kwargs):
        serializer = StringingOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        deposit = data.pop("deposit", None)
        try:
            order, created = run_service(
                take_in_order,
                user=request.user,
                deposit=dict(deposit) if deposit else None,
                **data,
            )
        except IntegrityError:
            # A concurrent request with the same client_transaction_id won the
            # race: hand back the caller's own order, refuse anyone else's key.
            key = data.get("client_transaction_id")
            existing = (
                key and StringingOrder.objects.filter(client_transaction_id=key).first()
            )
            if not existing:
                raise
            if existing.created_by_id != request.user.pk:
                raise ValidationError(
                    {
                        "client_transaction_id": [
                            "This order id was already used. Start a new order."
                        ]
                    }
                ) from None
            order, created = existing, False
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return detail_response(request, order.pk, code)


class StringingStatusCountsView(APIView):
    """GET: order counts per status for the list filters (specs/007 R5)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(run_service(status_counts, request.query_params))


class StringingOrderDetailView(APIView):
    """GET: details. PATCH: edit (FR-007–009). No DELETE (FR-024)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        return detail_response(request, pk)

    def patch(self, request, pk):
        get_order(pk)
        serializer = StringingOrderWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = serializer.validated_data

        if "direct_cost" in changes and not can_view_financials(request.user):
            raise PermissionDenied("You do not have permission to change direct cost.")

        run_service(update_stringing_order, order_id=pk, user=request.user, **changes)
        return detail_response(request, pk)


class StringingOrderStatusView(APIView):
    """POST: move the order along the workflow (FR-010–013)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        get_order(pk)
        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            change_status(
                order_id=pk,
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
        return detail_response(request, pk)


class StringingOrderCancelView(APIView):
    """POST: cancel with a reason (FR-021–023)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.has_perm(CANCEL_PERMISSION):
            raise PermissionDenied(
                "You do not have permission to cancel stringing orders."
            )
        get_order(pk)
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_service(
            cancel_stringing_order,
            order_id=pk,
            user=request.user,
            reason=serializer.validated_data["reason"],
            materials_used=serializer.validated_data["materials_used"],
        )
        return detail_response(request, pk)


class StringingOrderPaymentsView(generics.ListAPIView):
    """GET: the order's payments, newest first. POST: receipt or refund."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrderPaymentSerializer
    filter_backends = []

    def get_queryset(self):
        order = get_order(self.kwargs["pk"])
        return (
            Payment.objects.filter(stringing_order=order)
            .select_related("received_by")
            .order_by("-payment_date", "-id")
        )

    def post(self, request, pk):
        serializer = OrderPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data["payment_type"] == Payment.PaymentType.REFUND:
            if not request.user.has_perm(REFUND_PERMISSION):
                raise PermissionDenied("You do not have permission to process refunds.")
        elif not request.user.has_perm(RECORD_PAYMENT_PERMISSION):
            raise PermissionDenied("You do not have permission to record payments.")

        get_order(pk)
        payment, _ = run_service(
            record_order_payment, order_id=pk, user=request.user, **data
        )
        order = get_object_or_404(order_queryset(), pk=pk)
        return Response(
            {
                "payment": OrderPaymentSerializer(payment).data,
                "order": StringingOrderDetailSerializer(
                    order, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class StringingOrderHistoryView(APIView):
    """GET: audit history, oldest first (FR-025)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        order = get_order(pk)
        entries = order_history(
            order, can_view_financials=can_view_financials(request.user)
        )
        return Response(entries)


class StringingRevenueReportView(APIView):
    """GET: revenue and profit for a date range (FR-026–028)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_view_financials(request.user):
            raise PermissionDenied(
                "You do not have permission to view stringing financials."
            )
        query = RevenueReportQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        report = run_service(revenue_report, **query.validated_data)
        return Response(RevenueReportSerializer(report).data)
