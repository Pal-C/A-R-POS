from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.models import Customer
from customers.selectors import (
    phone_matches,
    preorder_history,
    sales_history,
    search_customers,
    stringing_history,
)
from customers.serializers import (
    CustomerDetailSerializer,
    CustomerListSerializer,
    CustomerPreorderHistorySerializer,
    CustomerSaleHistorySerializer,
    CustomerStringingHistorySerializer,
    CustomerWriteSerializer,
)
from customers.services import archive_customer, delete_customer, reactivate_customer

ARCHIVE_PERMISSION = "customers.archive_customer"
DELETE_PERMISSION = "customers.delete_customer"


def run_service(func, *args, **kwargs):
    """Calls a service or selector, converting Django validation errors to HTTP 400."""
    try:
        return func(*args, **kwargs)
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        raise ValidationError(detail) from None


def customer_response(customer, status_code=status.HTTP_200_OK, *, warn_phone=False):
    """Detail payload, optionally with the duplicate-phone warning list (FR-003)."""
    data = CustomerDetailSerializer(customer).data
    if warn_phone:
        data["duplicate_phone_customers"] = CustomerListSerializer(
            phone_matches(customer.phone_number, exclude_id=customer.pk),
            many=True,
        ).data
    return Response(data, status=status_code)


class CustomerListCreateView(generics.ListCreateAPIView):
    """
    GET: paged customer list with ``search`` and ``status`` filters.
    POST: create a customer; the response lists other active customers with
    the same phone number.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CustomerWriteSerializer
        return CustomerListSerializer

    def create(self, request, *args, **kwargs):
        serializer = CustomerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = run_service(serializer.save)
        return customer_response(customer, status.HTTP_201_CREATED, warn_phone=True)

    def get_queryset(self):
        params = self.request.query_params
        return run_service(
            search_customers,
            params.get("search", ""),
            params.get("status", "active"),
        )


class CustomerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: customer details.
    PATCH: edit the customer; the response lists other active customers with
    the same phone number.
    DELETE: permanently delete a customer with no history
    (requires customers.delete_customer).
    """

    permission_classes = [IsAuthenticated]
    queryset = Customer.objects.all()
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return CustomerWriteSerializer
        return CustomerDetailSerializer

    def update(self, request, *args, **kwargs):
        serializer = CustomerWriteSerializer(
            self.get_object(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        customer = run_service(serializer.save)
        return customer_response(customer, warn_phone=True)

    def destroy(self, request, *args, **kwargs):
        if not request.user.has_perm(DELETE_PERMISSION):
            raise PermissionDenied("You do not have permission to delete customers.")

        customer = self.get_object()
        run_service(delete_customer, customer.pk, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PhoneMatchesView(APIView):
    """GET ?phone=&exclude_id=: active customers sharing a phone number."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        exclude_id = request.query_params.get("exclude_id")
        matches = phone_matches(
            request.query_params.get("phone", ""),
            exclude_id=int(exclude_id) if exclude_id and exclude_id.isdigit() else None,
        )
        return Response(CustomerListSerializer(matches, many=True).data)


class CustomerHistoryView(generics.ListAPIView):
    """Paged history list for one customer; 404 for unknown customers."""

    permission_classes = [IsAuthenticated]
    selector = None

    def get_queryset(self):
        customer = get_object_or_404(Customer, pk=self.kwargs["pk"])
        return type(self).selector(customer)


class CustomerSalesView(CustomerHistoryView):
    serializer_class = CustomerSaleHistorySerializer
    selector = staticmethod(sales_history)


class CustomerStringingOrdersView(CustomerHistoryView):
    serializer_class = CustomerStringingHistorySerializer
    selector = staticmethod(stringing_history)


class CustomerPreordersView(CustomerHistoryView):
    serializer_class = CustomerPreorderHistorySerializer
    selector = staticmethod(preorder_history)


class CustomerArchiveActionView(APIView):
    """POST: archive or reactivate (requires customers.archive_customer)."""

    permission_classes = [IsAuthenticated]
    service = None

    def post(self, request, pk):
        if not request.user.has_perm(ARCHIVE_PERMISSION):
            raise PermissionDenied(
                "You do not have permission to archive or reactivate customers."
            )

        get_object_or_404(Customer, pk=pk)
        customer = run_service(type(self).service, pk, request.user)
        return customer_response(customer)


class ArchiveCustomerView(CustomerArchiveActionView):
    service = staticmethod(archive_customer)


class ReactivateCustomerView(CustomerArchiveActionView):
    service = staticmethod(reactivate_customer)
