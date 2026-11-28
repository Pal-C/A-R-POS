"""
Read queries for stringing orders: payment-state annotations, search,
audit history and the revenue report.

Amount paid always comes from the shared net-paid rule in
``sales.selectors`` so stringing, sales and customer summaries agree.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import (
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
from django.utils.dateparse import parse_date

from customers.phone import is_phone_query, normalize_phone
from sales.models import Payment
from sales.selectors import MONEY, ZERO, net_paid_subquery
from stringing.models import StringingOrder, StringingOrderEvent


class PaymentState:
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    PAID = "PAID"

    values = (UNPAID, PARTIAL, PAID)


# Service plus add-ons, minus discount (specs/007 R1); see
# StringingOrder.total_amount.
ORDER_TOTAL = ExpressionWrapper(
    F("service_price") + F("stencil_price") + F("grip_price") - F("discount_amount"),
    output_field=MONEY,
)

# Completed and paid in full; see StringingOrder.is_settled.
SETTLED = Q(status=StringingOrder.Status.COMPLETED, paid_in_full_at__isnull=False)

ORDERINGS = {
    "-created_at": ("-created_at", "-id"),
    "created_at": ("created_at", "id"),
    "status": ("status", "-created_at", "-id"),
}


def store_tz():
    return ZoneInfo(settings.STORE_TIME_ZONE)


def local_day_range(date_from, date_to):
    """Aware [start, end) datetimes covering store-local dates, inclusive."""
    tz = store_tz()
    start = datetime.combine(date_from, time.min, tzinfo=tz)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz)
    return start, end


def annotate_payment_state(queryset):
    """
    Adds ``order_total``, ``amount_paid`` (net of refunds) and
    ``payment_state`` to a StringingOrder queryset, in the same query.
    """
    queryset = queryset.annotate(
        order_total=ORDER_TOTAL,
        amount_paid=net_paid_subquery("stringing_order"),
    )
    return queryset.annotate(
        payment_state=Case(
            # Settled orders (completed and paid in full) stay PAID after a
            # refund made after pickup.
            When(SETTLED, then=Value(PaymentState.PAID)),
            When(amount_paid__gte=F("order_total"), then=Value(PaymentState.PAID)),
            When(amount_paid__gt=0, then=Value(PaymentState.PARTIAL)),
            default=Value(PaymentState.UNPAID),
            output_field=CharField(),
        )
    )


def order_queryset():
    """Orders with everything the list and detail serializers read."""
    return annotate_payment_state(
        StringingOrder.objects.select_related("customer", "created_by", "cancelled_by")
    )


# ---------------------------------------------------------------------------
# Search (US4)
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


def search_orders(params):
    """
    Filtered, ordered order queryset (FR-018–020). ``params`` is a mapping
    of query parameters; invalid values raise a field-keyed
    ValidationError.
    """
    queryset = filter_orders(order_queryset(), params)

    ordering = params.get("ordering") or "-created_at"
    if ordering not in ORDERINGS:
        raise ValidationError({"ordering": [f"Use one of: {', '.join(ORDERINGS)}."]})
    return queryset.order_by(*ORDERINGS[ordering])


def status_counts(params):
    """
    Order counts per status for the list filters in ``params``, ignoring
    ``status`` (specs/007 R5). One aggregate query. Returns
    ``{"all": n, "RECEIVED": n, ...}``.
    """
    queryset = filter_orders(
        annotate_payment_state(StringingOrder.objects.all()),
        params,
        with_status=False,
    )
    counts = {"all": Count("pk")}
    for value in StringingOrder.Status.values:
        counts[value] = Count("pk", filter=Q(status=value))
    return queryset.aggregate(**counts)


def filter_orders(queryset, params, *, with_status=True):
    """
    Applies the list's search and filters to an order queryset annotated
    with ``annotate_payment_state``. ``status`` is skipped when
    ``with_status`` is false.
    """

    search = (params.get("search") or "").strip()
    if search:
        matches = (
            Q(order_number__icontains=search)
            | Q(racket_description__icontains=search)
            | Q(string_type__icontains=search)
            | Q(customer__full_name__icontains=search)
        )
        if is_phone_query(search):
            digits = normalize_phone(search)
            if digits:
                matches |= Q(customer__phone_normalized__contains=digits)
        queryset = queryset.filter(matches)

    statuses = [s for s in (params.get("status") or "").split(",") if s.strip()]
    if statuses and with_status:
        statuses = [s.strip().upper() for s in statuses]
        invalid = [s for s in statuses if s not in StringingOrder.Status.values]
        if invalid:
            raise ValidationError(
                {"status": [f"Unknown status: {', '.join(invalid)}."]}
            )
        queryset = queryset.filter(status__in=statuses)

    payment_state = (params.get("payment_state") or "").strip().upper()
    if payment_state:
        if payment_state not in PaymentState.values:
            raise ValidationError({"payment_state": ["Use UNPAID, PARTIAL or PAID."]})
        # Cancelled orders owe nothing; they never match a payment state.
        queryset = queryset.filter(payment_state=payment_state).exclude(
            status=StringingOrder.Status.CANCELLED
        )

    customer = (params.get("customer") or "").strip()
    if customer:
        if not customer.isdecimal() or not customer.isascii():
            raise ValidationError({"customer": ["Enter a customer id."]})
        queryset = queryset.filter(customer_id=int(customer))

    received_from = _parse_date_param(params, "received_from")
    received_to = _parse_date_param(params, "received_to")
    if received_from and received_to and received_from > received_to:
        raise ValidationError(
            {"received_to": ["End date must be on or after the start date."]}
        )
    if received_from:
        queryset = queryset.filter(
            created_at__gte=local_day_range(received_from, received_from)[0]
        )
    if received_to:
        queryset = queryset.filter(
            created_at__lt=local_day_range(received_to, received_to)[1]
        )
    return queryset


# ---------------------------------------------------------------------------
# Audit history (US5)
# ---------------------------------------------------------------------------

_FINANCIAL_CHANGE_FIELDS = {"direct_cost"}


def _user_ref(user):
    return {"id": user.pk, "username": user.get_username()}


def order_history(order, *, can_view_financials):
    """
    Events and payments for one order, oldest first (FR-025). Direct-cost
    changes are removed for users without the financials permission.
    """
    entries = []

    for event in order.events.select_related("performed_by"):
        entry = {
            "type": event.event_type,
            "at": event.created_at,
            "by": _user_ref(event.performed_by),
        }
        if event.event_type in (
            StringingOrderEvent.EventType.STATUS_CHANGED,
            StringingOrderEvent.EventType.CANCELLED,
        ):
            entry["from_status"] = event.from_status
            entry["to_status"] = event.to_status
        if event.event_type == StringingOrderEvent.EventType.UPDATED:
            changes = dict(event.changes)
            if not can_view_financials:
                for field in _FINANCIAL_CHANGE_FIELDS:
                    changes.pop(field, None)
                if not changes:
                    continue
            entry["changes"] = changes
        if event.reason:
            entry["reason"] = event.reason
        entries.append(entry)

    for payment in Payment.objects.filter(stringing_order=order).select_related(
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


# ---------------------------------------------------------------------------
# Revenue and profit (US6)
# ---------------------------------------------------------------------------


def _money_sum(expression, condition):
    return Coalesce(Sum(expression, filter=condition), ZERO, output_field=MONEY)


def revenue_report(date_from, date_to):
    """
    Stringing revenue for store-local dates ``date_from``..``date_to``
    inclusive (FR-026–028, research R3). An order is counted once it is
    paid in full, on its ``paid_in_full_at`` date; cancelled orders never
    count. Refunds on completed orders made after pickup are reported
    separately by refund date and deducted in the "after refunds" totals.
    Runs three aggregate queries.
    """
    if date_from > date_to:
        raise ValidationError(
            {"date_to": ["End date must be on or after the start date."]}
        )

    start, end = local_day_range(date_from, date_to)
    not_cancelled = ~Q(status=StringingOrder.Status.CANCELLED)
    recognized = (
        not_cancelled & Q(paid_in_full_at__gte=start) & Q(paid_in_full_at__lt=end)
    )
    cancelled = Q(cancelled_at__gte=start) & Q(cancelled_at__lt=end)

    totals = StringingOrder.objects.filter(recognized | cancelled).aggregate(
        orders_count=Count("pk", filter=recognized),
        gross_service_price=_money_sum("service_price", recognized),
        gross_add_ons=_money_sum(F("stencil_price") + F("grip_price"), recognized),
        total_discounts=_money_sum("discount_amount", recognized),
        total_direct_cost=_money_sum("direct_cost", recognized),
        cancelled_count=Count("pk", filter=cancelled),
    )

    unpaid = (
        StringingOrder.objects.filter(
            not_cancelled,
            paid_in_full_at__isnull=True,
            created_at__gte=start,
            created_at__lt=end,
        )
        .annotate(
            order_total=ORDER_TOTAL,
            amount_paid=net_paid_subquery("stringing_order"),
        )
        .aggregate(
            unpaid_count=Count("pk"),
            outstanding_balance=Coalesce(
                Sum(F("order_total") - F("amount_paid"), output_field=MONEY),
                ZERO,
                output_field=MONEY,
            ),
        )
    )

    refunds = Payment.objects.filter(
        Q(payment_date__gte=start)
        & Q(payment_date__lt=end)
        # Only refunds made after pickup; earlier refunds reopened the
        # balance and had to be paid again before completion.
        & Q(payment_date__gte=F("stringing_order__completed_at")),
        stringing_order__status=StringingOrder.Status.COMPLETED,
        payment_type=Payment.PaymentType.REFUND,
        status=Payment.Status.POSTED,
    )
    total_refunds = refunds.aggregate(
        total=Coalesce(Sum("amount"), ZERO, output_field=MONEY)
    )["total"]

    net_revenue = (
        totals["gross_service_price"]
        + totals["gross_add_ons"]
        - totals["total_discounts"]
    )
    profit = net_revenue - totals["total_direct_cost"]
    return {
        "date_from": date_from,
        "date_to": date_to,
        "orders_count": totals["orders_count"],
        "gross_service_price": totals["gross_service_price"],
        "gross_add_ons": totals["gross_add_ons"],
        "total_discounts": totals["total_discounts"],
        "net_revenue": net_revenue,
        "total_direct_cost": totals["total_direct_cost"],
        "profit": profit,
        "total_refunds": total_refunds,
        "net_revenue_after_refunds": net_revenue - total_refunds,
        "profit_after_refunds": profit - total_refunds,
        "cancelled_count": totals["cancelled_count"],
        "unpaid_count": unpaid["unpaid_count"],
        "outstanding_balance": unpaid["outstanding_balance"],
    }
