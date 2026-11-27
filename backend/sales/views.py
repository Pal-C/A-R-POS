from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sales.models import Payment, Sale, SaleItem
from sales.serializers import (
    CheckoutSerializer,
    DraftCartSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
    SaleCreateSerializer,
    SaleCustomerChangeSerializer,
    SaleDetailSerializer,
    SaleItemAddSerializer,
    SaleItemSerializer,
    SaleItemUpdateSerializer,
    SaleListSerializer,
    SaleUpdateSerializer,
)
from sales.services import (
    cancel_sale,
    change_sale_customer,
    checkout_sale,
    finalize_sale,
    remove_sale_item,
    replace_draft_cart,
)

CANCEL_PERMISSION = "sales.cancel_sale"
REFUND_PERMISSION = "sales.process_refund"
RECORD_PAYMENT_PERMISSION = "sales.record_payment"


def handle_service_validation_error(exc):
    # Keep field-keyed errors ({"items": [...]}) so the UI can place them.
    detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
    raise ValidationError(detail)


def run_service(func, *args, **kwargs):
    """Calls a service, converting Django validation errors to HTTP 400."""
    try:
        return func(*args, **kwargs)
    except DjangoValidationError as exc:
        handle_service_validation_error(exc)


def sale_detail_queryset():
    return Sale.objects.select_related(
        "customer", "created_by", "cancelled_by"
    ).prefetch_related(
        "items__product",
        "payments__received_by",
        "events__performed_by",
    )


def sale_detail_response(request, sale_id, status_code=status.HTTP_200_OK):
    sale = sale_detail_queryset().get(pk=sale_id)
    data = SaleDetailSerializer(sale, context={"request": request}).data
    return Response(data, status=status_code)


class SaleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Sale.objects.select_related("customer", "created_by")
            .prefetch_related(
                "payments",
                Prefetch("items", queryset=SaleItem.objects.select_related("product")),
            )
            .order_by("-sale_date", "-created_at", "-id")
        )

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(sale_number__icontains=search)
                | Q(customer__full_name__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SaleCreateSerializer
        return SaleListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = run_service(serializer.save)
        return sale_detail_response(request, sale.pk, status.HTTP_201_CREATED)


class SaleDetailView(generics.RetrieveUpdateAPIView):
    """GET a sale; PATCH a draft's customer or sale-level discount."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return sale_detail_queryset()

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return SaleUpdateSerializer
        return SaleDetailSerializer

    def update(self, request, *args, **kwargs):
        sale = self.get_object()
        serializer = SaleUpdateSerializer(sale, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        run_service(serializer.save)
        return sale_detail_response(request, sale.pk)


class SaleItemAddView(APIView):
    """POST a product onto a draft sale (merges into an existing line)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        serializer = SaleItemAddSerializer(
            data=request.data,
            context={"request": request, "sale": sale},
        )
        serializer.is_valid(raise_exception=True)
        run_service(serializer.save)
        return sale_detail_response(request, sale.pk, status.HTTP_201_CREATED)


class SaleItemDetailView(APIView):
    """PATCH or DELETE a line on a draft sale."""

    permission_classes = [IsAuthenticated]

    def get_item(self, pk, item_pk):
        return get_object_or_404(
            SaleItem.objects.select_related("product"),
            pk=item_pk,
            sale_id=pk,
        )

    def get(self, request, pk, item_pk):
        item = self.get_item(pk, item_pk)
        return Response(SaleItemSerializer(item, context={"request": request}).data)

    def patch(self, request, pk, item_pk):
        item = self.get_item(pk, item_pk)
        serializer = SaleItemUpdateSerializer(item, data=request.data)
        serializer.is_valid(raise_exception=True)
        run_service(serializer.save)
        return sale_detail_response(request, pk)

    def delete(self, request, pk, item_pk):
        item = self.get_item(pk, item_pk)
        run_service(remove_sale_item, sale_id=pk, item_id=item.pk)
        return sale_detail_response(request, pk)


class FinalizeSaleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        get_object_or_404(Sale, pk=pk)
        run_service(finalize_sale, sale_id=pk, user=request.user)
        return sale_detail_response(request, pk)


class CancelSaleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.has_perm(CANCEL_PERMISSION):
            raise PermissionDenied("You do not have permission to cancel sales.")

        get_object_or_404(Sale, pk=pk)
        run_service(
            cancel_sale,
            sale_id=pk,
            user=request.user,
            reason=request.data.get("reason", ""),
        )
        return sale_detail_response(request, pk)


class PaymentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Payment.objects.select_related(
            "sale",
            "stringing_order",
            "preorder",
            "received_by",
        )

        sale_id = self.request.query_params.get("sale_id")
        if sale_id:
            queryset = queryset.filter(sale_id=sale_id)

        stringing_order_id = self.request.query_params.get("stringing_order_id")
        if stringing_order_id:
            queryset = queryset.filter(stringing_order_id=stringing_order_id)

        preorder_id = self.request.query_params.get("preorder_id")
        if preorder_id:
            queryset = queryset.filter(preorder_id=preorder_id)

        payment_type = self.request.query_params.get("payment_type")
        if payment_type:
            queryset = queryset.filter(payment_type=payment_type)

        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PaymentCreateSerializer
        return PaymentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_refund = (
            serializer.validated_data["payment_type"] == Payment.PaymentType.REFUND
        )
        if is_refund and not request.user.has_perm(REFUND_PERMISSION):
            raise PermissionDenied("You do not have permission to process refunds.")
        if not is_refund and not request.user.has_perm(RECORD_PAYMENT_PERMISSION):
            raise PermissionDenied("You do not have permission to record payments.")

        payment = run_service(serializer.save)

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class CheckoutView(APIView):
    """Creates, finalizes and optionally pays a sale in one step (specs/006 R1)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        payment = data.pop("payment", None)
        try:
            sale, created = run_service(
                checkout_sale,
                user=request.user,
                payment=dict(payment) if payment else None,
                **data,
            )
        except IntegrityError:
            # A concurrent retry with the same client_transaction_id won the race.
            existing = Sale.objects.filter(
                client_transaction_id=data.get("client_transaction_id")
            ).first()
            if not existing:
                raise
            sale, created = existing, False
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return sale_detail_response(request, sale.pk, code)


class DraftCartView(APIView):
    """PUT replaces a draft's whole cart (specs/006 R2)."""

    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        get_object_or_404(Sale, pk=pk)
        serializer = DraftCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_service(replace_draft_cart, sale_id=pk, **serializer.validated_data)
        return sale_detail_response(request, pk)


class SaleCustomerView(APIView):
    """POST links or changes the customer of a finalized sale, with a reason."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        get_object_or_404(Sale, pk=pk)
        serializer = SaleCustomerChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_service(
            change_sale_customer,
            sale_id=pk,
            user=request.user,
            customer=serializer.validated_data["customer"],
            reason=serializer.validated_data["reason"],
        )
        return sale_detail_response(request, pk)
