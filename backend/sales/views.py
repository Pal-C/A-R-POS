from django.shortcuts import render

# Create your views here.

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from sales.models import Sale, Payment
from sales.serializers import (
    SaleListSerializer,
    SaleDetailSerializer,
    SaleCreateSerializer,
    PaymentSerializer,
    PaymentCreateSerializer,
)
from sales.services import finalize_sale, cancel_sale


def handle_service_validation_error(exc):
    raise ValidationError(exc.messages)


class SaleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Sale.objects
            .select_related("customer", "created_by")
            .prefetch_related("items__product", "payments")
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

        try:
            sale = serializer.save()
        except DjangoValidationError as exc:
            handle_service_validation_error(exc)

        return Response(
            SaleDetailSerializer(sale).data,
            status=status.HTTP_201_CREATED,
    )


class SaleDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SaleDetailSerializer
    queryset = (
        Sale.objects
        .select_related("customer", "created_by", "cancelled_by")
        .prefetch_related("items__product", "payments")
    )


class FinalizeSaleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            sale = finalize_sale(
                sale_id=pk,
                user=request.user,
            )
        except DjangoValidationError as exc:
            handle_service_validation_error(exc)

        return Response(
            SaleDetailSerializer(sale).data,
            status=status.HTTP_200_OK,
        )


class CancelSaleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reason = request.data.get("reason", "")

        try:
            sale = cancel_sale(
                sale_id=pk,
                user=request.user,
                reason=reason,
            )
        except DjangoValidationError as exc:
            handle_service_validation_error(exc)

        return Response(
            SaleDetailSerializer(sale).data,
            status=status.HTTP_200_OK,
        )


class PaymentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Payment.objects
            .select_related(
                "sale",
                "stringing_order",
                "preorder",
                "received_by",
            )
        )

        sale_id = self.request.query_params.get("sale_id")
        if sale_id:
            queryset = queryset.filter(sale_id=sale_id)

        stringing_order_id = self.request.query_params.get(
            "stringing_order_id"
        )
        if stringing_order_id:
            queryset = queryset.filter(
                stringing_order_id=stringing_order_id
            )

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

        try:
            payment = serializer.save()
        except DjangoValidationError as exc:
            handle_service_validation_error(exc)

        response_serializer = PaymentSerializer(payment)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )
