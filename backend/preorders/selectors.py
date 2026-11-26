"""
Read queries for pre-orders: payment-state annotations, search, the
per-product waiting summary and audit history.

Amount paid always comes from the shared net-paid rule in
``sales.selectors`` so pre-orders, sales and customer summaries agree.
"""

from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date

from customers.phone import is_phone_query, normalize_phone
from preorders.models import PreOrder, PreOrderEvent
from sales.models import Payment
from sales.selectors import MONEY, net_paid_subquery

Status = PreOrder.Status
OPEN_STATUSES = (Status.PENDING, Status.ORDERED, Status.ARRIVED)
WAITING_FOR_SUPPLIER = (Status.PENDING, Status.ORDERED)


class PaymentState:
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    PAID = "PAID"

    values = (UNPAID, PARTIAL, PAID)


ORDER_TOTAL = ExpressionWrapper(
    F("quantity") * F("agreed_unit_price"), output_field=MONEY
)

ORDERINGS = {
    "-created_at": (F("created_at").desc(), F("id").desc()),
    "created_at": (F("created_at").asc(), F("id").asc()),
    "expected_arrival_date": (
        F("expected_arrival_date").asc(nulls_last=True),
        F("created_at").asc(),
        F("id").asc(),
    ),
}


def store_today():
    """Today's date in the store's time zone."""
    return timezone.now().astimezone(ZoneInfo(settings.STORE_TIME_ZONE)).date()


def annotate_payment_state(queryset):
    """
    Adds ``order_total``, ``amount_paid`` (net of refunds),
    ``payment_state`` and ``is_overdue`` to a PreOrder queryset, in the
    same query. Settled pre-orders are always PAID.
    """
    queryset = queryset.annotate(
        order_total=ORDER_TOTAL,
        amount_paid=net_paid_subquery("preorder"),
    )
    return queryset.annotate(
        payment_state=Case(
            # Settled pre-orders stay PAID after a refund made after handover.
            When(
                status=Status.FULFILLED,
                settled_at__isnull=False,
                then=Value(PaymentState.PAID),
            ),
            When(amount_paid__gte=F("order_total"), then=Value(PaymentState.PAID)),
            When(amount_paid__gt=0, then=Value(PaymentState.PARTIAL)),
            default=Value(PaymentState.UNPAID),
            output_field=CharField(),
        ),
        is_overdue=Case(
            When(
                Q(expected_arrival_date__lt=store_today())
                & Q(status__in=WAITING_FOR_SUPPLIER),
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )


def preorder_queryset():
    """Pre-orders with everything the list and detail serializers read."""
    return annotate_payment_state(
        PreOrder.objects.select_related(
            "customer", "product", "created_by", "fulfilled_by", "cancelled_by"
        )
    )


# ---------------------------------------------------------------------------
# Search (US5)
# ---------------------------------------------------------------------------


def _parse_date_param(params, name):
    raw = params.get(name)
    if not raw:
        return None
    try:
        value = parse_date(raw)
    except ValueError:
        value = None
    if value is None:
        raise ValidationError({name: ["Enter a date as YYYY-MM-DD."]})
    return value


def _parse_id_param(params, name):
    raw = (params.get(name) or "").strip()
    if not raw:
        return None
    if not (raw.isascii() and raw.isdecimal()):
        raise ValidationError({name: ["Enter an id."]})
    return int(raw)


def search_preorders(params):
    """
    Filtered, ordered pre-order queryset (FR-018–020). ``params`` is a
    mapping of query parameters; invalid values raise a field-keyed
    ValidationError.
    """
    queryset = preorder_queryset()

    search = (params.get("search") or "").strip()
    if search:
        matches = (
            Q(order_number__icontains=search)
            | Q(customer__full_name__icontains=search)
            | Q(product__name__icontains=search)
            | Q(product__sku__icontains=search)
        )
        if is_phone_query(search):
            digits = normalize_phone(search)
            if digits:
                matches |= Q(customer__phone_normalized__contains=digits)
        queryset = queryset.filter(matches)

    statuses = [s.strip().upper() for s in (params.get("status") or "").split(",")]
    statuses = [s for s in statuses if s]
    if statuses:
        invalid = [s for s in statuses if s not in Status.values]
        if invalid:
            raise ValidationError(
                {"status": [f"Unknown status: {', '.join(invalid)}."]}
            )
        queryset = queryset.filter(status__in=statuses)

    payment_state = (params.get("payment_state") or "").strip().upper()
    if payment_state:
        if payment_state not in PaymentState.values:
            raise ValidationError({"payment_state": ["Use UNPAID, PARTIAL or PAID."]})
        # Cancelled pre-orders owe nothing; they never match a payment state.
        queryset = queryset.filter(payment_state=payment_state).exclude(
            status=Status.CANCELLED
        )

    customer_id = _parse_id_param(params, "customer")
    if customer_id is not None:
        queryset = queryset.filter(customer_id=customer_id)

    product_id = _parse_id_param(params, "product")
    if product_id is not None:
        queryset = queryset.filter(product_id=product_id)

    expected_from = _parse_date_param(params, "expected_from")
    expected_to = _parse_date_param(params, "expected_to")
    if expected_from and expected_to and expected_from > expected_to:
        raise ValidationError(
            {"expected_to": ["End date must be on or after the start date."]}
        )
    if expected_from:
        queryset = queryset.filter(expected_arrival_date__gte=expected_from)
    if expected_to:
        queryset = queryset.filter(expected_arrival_date__lte=expected_to)

    overdue = (params.get("overdue") or "").strip().lower()
    if overdue:
        if overdue not in ("true", "false"):
            raise ValidationError({"overdue": ["Use true or false."]})
        queryset = queryset.filter(is_overdue=(overdue == "true"))

    ordering = params.get("ordering") or "-created_at"
    if ordering not in ORDERINGS:
        raise ValidationError({"ordering": [f"Use one of: {', '.join(ORDERINGS)}."]})
    return queryset.order_by(*ORDERINGS[ordering])


# ---------------------------------------------------------------------------
# Per-product waiting summary (US3)
# ---------------------------------------------------------------------------


def product_preorder_summary(product):
    """
    Units and orders waiting per open status for one product, plus its
    ORDERED pre-orders oldest first (for choosing orders on arrival).
    Two queries.
    """
    aggregates = {}
    for status in OPEN_STATUSES:
        condition = Q(status=status)
        aggregates[f"{status}_orders"] = Count("pk", filter=condition)
        aggregates[f"{status}_units"] = Coalesce(Sum("quantity", filter=condition), 0)

    totals = PreOrder.objects.filter(product=product).aggregate(**aggregates)

    ordered = list(
        preorder_queryset()
        .filter(product=product, status=Status.ORDERED)
        .order_by("created_at", "id")
    )

    return {
        "product": product,
        "waiting": {
            status: {
                "orders": totals[f"{status}_orders"],
                "units": totals[f"{status}_units"],
            }
            for status in OPEN_STATUSES
        },
        "ordered_preorders": ordered,
    }


# ---------------------------------------------------------------------------
# Audit history (US6)
# ---------------------------------------------------------------------------


def _user_ref(user):
    return {"id": user.pk, "username": user.get_username()}


def preorder_history(preorder):
    """Events and payments for one pre-order, oldest first (FR-025)."""
    entries = []

    for event in preorder.events.select_related("performed_by"):
        entry = {
            "type": event.event_type,
            "at": event.created_at,
            "by": _user_ref(event.performed_by),
        }
        if event.event_type in (
            PreOrderEvent.EventType.STATUS_CHANGED,
            PreOrderEvent.EventType.CANCELLED,
        ):
            entry["from_status"] = event.from_status
            entry["to_status"] = event.to_status
        if event.changes:
            entry["changes"] = event.changes
        if event.extra:
            entry.update(event.extra)
        if event.reason:
            entry["reason"] = event.reason
        entries.append(entry)

    for payment in Payment.objects.filter(preorder=preorder).select_related(
        "received_by"
    ):
        entries.append(
            {
                "type": "PAYMENT",
                "at": payment.payment_date,
                "by": _user_ref(payment.received_by),
                "payment_id": payment.pk,
                "payment_type": payment.payment_type,
                "amount": f"{payment.amount:.2f}",
                "payment_method": payment.payment_method,
                "status": payment.status,
                "notes": payment.notes,
            }
        )

    entries.sort(key=lambda entry: entry["at"])
    return entries
