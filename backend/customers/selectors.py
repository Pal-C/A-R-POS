"""
Read-side queries for customers: search, duplicate-phone lookup, summary
totals and history lists. Nothing here writes to the database.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Case, Count, ExpressionWrapper, F, Q, Sum, When
from django.db.models.functions import Coalesce

from customers.models import Customer, CustomerAuditEvent
from customers.phone import is_phone_query, normalize_phone
from preorders.models import PreOrder
from sales.models import Payment, Sale
from sales.selectors import MONEY, ZERO, net_paid_expression, net_paid_subquery
from stringing.models import StringingOrder

# Sales that are real transactions for history and totals (drafts are carts).
FINALIZED_SALE = ~Q(status=Sale.Status.DRAFT)
OPEN_SALE_STATUSES = (Sale.Status.PENDING_PAYMENT, Sale.Status.COMPLETED)
STRINGING_TOTAL = ExpressionWrapper(
    F("service_price") - F("discount_amount"), output_field=MONEY
)
PREORDER_TOTAL = ExpressionWrapper(
    F("quantity") * F("agreed_unit_price"), output_field=MONEY
)

STATUS_FILTERS = {
    "active": {"is_active": True},
    "archived": {"is_active": False},
    "all": {},
}


def search_customers(query="", status="active"):
    """
    Customers ordered by name, filtered by archive status and an optional
    search: phone-like text matches the normalized phone, anything else
    matches the name (case-insensitive substring).
    """
    if status not in STATUS_FILTERS:
        raise ValidationError(
            {"status": f"Use one of: {', '.join(STATUS_FILTERS)}."}
        )

    queryset = Customer.objects.filter(**STATUS_FILTERS[status])
    query = (query or "").strip()

    if query:
        if is_phone_query(query):
            queryset = queryset.filter(
                phone_normalized__contains=normalize_phone(query)
            )
        else:
            queryset = queryset.filter(full_name__icontains=query)

    return queryset.order_by("full_name", "id")


PHONE_MATCH_LIMIT = 5


def phone_matches(phone, exclude_id=None):
    """
    Active customers whose normalized phone equals ``phone``'s, for the
    duplicate-phone warning (FR-003). Empty or non-numeric input matches
    nothing.
    """
    normalized = normalize_phone(phone)
    if not normalized:
        return Customer.objects.none()

    queryset = Customer.objects.filter(is_active=True, phone_normalized=normalized)
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    return queryset.order_by("full_name", "id")[:PHONE_MATCH_LIMIT]


# ---------------------------------------------------------------------------
# Summary and history (US4)
# ---------------------------------------------------------------------------


def _sum(expression, **kwargs):
    return Coalesce(
        Sum(expression, output_field=MONEY, **kwargs), ZERO, output_field=MONEY
    )


def customer_summary(customer):
    """
    Counts and money totals for one customer (data-model.md "Derived:
    Customer Summary"), in a fixed number of queries.

    total_spent: net paid on finalized, non-cancelled sales.
    outstanding_balance: total minus net paid over non-cancelled sales,
    stringing orders and pre-orders. Receipts never exceed an order's total
    (sales.services.record_payment), so per-order balances are never
    negative and the sums can be subtracted.
    """
    not_cancelled = ~Q(status="CANCELLED")

    sales = Sale.objects.filter(FINALIZED_SALE, customer=customer).aggregate(
        count=Count("id"),
        owed=_sum("total_amount", filter=not_cancelled),
    )
    sales_paid = Payment.objects.filter(
        sale__customer=customer, sale__status__in=OPEN_SALE_STATUSES
    ).aggregate(net=net_paid_expression())["net"]

    stringing = StringingOrder.objects.filter(customer=customer).aggregate(
        count=Count("id"),
        owed=_sum(STRINGING_TOTAL, filter=not_cancelled),
        unfinished=Count(
            "id",
            filter=~Q(
                status__in=[
                    StringingOrder.Status.COMPLETED,
                    StringingOrder.Status.CANCELLED,
                ]
            ),
        ),
    )
    stringing_paid = Payment.objects.filter(
        stringing_order__customer=customer
    ).exclude(
        stringing_order__status=StringingOrder.Status.CANCELLED
    ).aggregate(net=net_paid_expression())["net"]

    preorders = PreOrder.objects.filter(customer=customer).aggregate(
        count=Count("id"),
        owed=_sum(PREORDER_TOTAL, filter=not_cancelled),
        open=Count(
            "id",
            filter=~Q(
                status__in=[PreOrder.Status.FULFILLED, PreOrder.Status.CANCELLED]
            ),
        ),
    )
    preorders_paid = Payment.objects.filter(
        preorder__customer=customer
    ).exclude(
        preorder__status=PreOrder.Status.CANCELLED
    ).aggregate(net=net_paid_expression())["net"]

    outstanding = (
        sales["owed"] - sales_paid
        + stringing["owed"] - stringing_paid
        + preorders["owed"] - preorders_paid
    )

    return {
        "sales_count": sales["count"],
        "stringing_orders_count": stringing["count"],
        "preorders_count": preorders["count"],
        "total_spent": sales_paid,
        "outstanding_balance": max(outstanding, Decimal("0.00")),
        "open_preorders_count": preorders["open"],
        "unfinished_stringing_orders_count": stringing["unfinished"],
    }


def sales_history(customer):
    """Finalized sales, newest first, with ``net_paid`` and ``outstanding``."""
    return (
        Sale.objects.filter(FINALIZED_SALE, customer=customer)
        .annotate(net_paid=net_paid_subquery("sale"))
        .annotate(
            outstanding=Case(
                When(status=Sale.Status.CANCELLED, then=ZERO),
                default=F("total_amount") - F("net_paid"),
                output_field=MONEY,
            )
        )
        .order_by("-finalized_at", "-id")
    )


def stringing_history(customer):
    """Stringing orders, newest first, with ``order_total``."""
    return (
        StringingOrder.objects.filter(customer=customer)
        .annotate(order_total=STRINGING_TOTAL)
        .order_by("-created_at", "-id")
    )


def preorder_history(customer):
    """Pre-orders, newest first, with ``order_total`` and ``net_paid``."""
    return (
        PreOrder.objects.filter(customer=customer)
        .select_related("product")
        .annotate(
            order_total=PREORDER_TOTAL,
            net_paid=net_paid_subquery("preorder"),
        )
        .order_by("-created_at", "-id")
    )


def last_archive_event(customer):
    """Latest ARCHIVED/REACTIVATED audit event for the customer, or None."""
    return (
        CustomerAuditEvent.objects.filter(
            customer_ref=customer.pk,
            action__in=[
                CustomerAuditEvent.Action.ARCHIVED,
                CustomerAuditEvent.Action.REACTIVATED,
            ],
        )
        .select_related("performed_by")
        .first()
    )
