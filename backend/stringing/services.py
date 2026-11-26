"""
Stringing order domain services (spec 002).

Lifecycle:

    RECEIVED ⇄ IN_PROGRESS ⇄ READY ──(balance 0)──▶ COMPLETED
        └───────────┴───────────┴──cancel(reason)──▶ CANCELLED

- Forward and backward moves are one step at a time; COMPLETED and
  CANCELLED are final.
- Money is recorded only as ``sales.Payment`` rows through
  ``sales.services.record_payment`` / ``process_refund``, which call
  ``sync_payment_state`` to keep ``paid_in_full_at`` (the revenue date)
  current.
- Every change writes an append-only ``StringingOrderEvent``.

All functions raise ``django.core.exceptions.ValidationError`` for
business-rule violations and ``StringingOrder.DoesNotExist`` for unknown
ids.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from customers.services import ensure_usable
from sales.models import Payment
from sales.selectors import net_paid_expression
from stringing.models import StringingOrder, StringingOrderEvent
from stringing.selectors import store_tz

ZERO = Decimal("0.00")

Status = StringingOrder.Status
EventType = StringingOrderEvent.EventType

ALLOWED_TRANSITIONS = {
    Status.RECEIVED: (Status.IN_PROGRESS,),
    Status.IN_PROGRESS: (Status.READY, Status.RECEIVED),
    Status.READY: (Status.COMPLETED, Status.IN_PROGRESS),
}

TEXT_FIELDS = ("racket_description", "string_type", "tension", "notes")
REQUIRED_TEXT_FIELDS = ("racket_description", "string_type")
MONEY_FIELDS = ("service_price", "discount_amount", "direct_cost")
EDITABLE_FIELDS = ("customer", *TEXT_FIELDS, *MONEY_FIELDS)


class StatusConflict(ValidationError):
    """The order's status changed since the client last read it."""

    def __init__(self, current_status):
        self.current_status = current_status
        super().__init__(
            "This order's status was changed by someone else. "
            f"It is now {Status(current_status).label}."
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _next_order_number():
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('stringing_order_number_seq')")
        (number,) = cursor.fetchone()
    year = timezone.now().astimezone(store_tz()).year
    return f"STR-{year}-{number:06d}"


def _lock_order(order_id):
    return StringingOrder.objects.select_for_update().get(pk=order_id)


def _net_paid(order):
    return Payment.objects.filter(stringing_order=order).aggregate(
        net=net_paid_expression()
    )["net"]


def _record_event(order, user, event_type, **fields):
    return StringingOrderEvent.objects.create(
        order=order, performed_by=user, event_type=event_type, **fields
    )


def _check_customer(customer):
    try:
        ensure_usable(customer)
    except ValidationError as exc:
        raise ValidationError({"customer": exc.messages}) from None


def _clean(values):
    """Validates and normalizes order fields; raises field-keyed errors."""
    errors = {}
    cleaned = dict(values)

    for field in TEXT_FIELDS:
        if field in cleaned:
            cleaned[field] = (cleaned[field] or "").strip()

    for field in REQUIRED_TEXT_FIELDS:
        if not cleaned.get(field):
            errors[field] = ["This field may not be blank."]

    for field in MONEY_FIELDS:
        value = cleaned.get(field)
        if value is None:
            errors[field] = ["This field is required."]
        elif value < 0:
            errors[field] = ["Must be zero or more."]

    price = cleaned.get("service_price")
    discount = cleaned.get("discount_amount")
    if (
        "service_price" not in errors
        and "discount_amount" not in errors
        and discount > price
    ):
        errors["discount_amount"] = ["Discount cannot be more than the price."]

    if errors:
        raise ValidationError(errors)
    return cleaned


def _audit_value(value):
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if hasattr(value, "pk"):
        return value.pk
    return value


# ---------------------------------------------------------------------------
# Payment state
# ---------------------------------------------------------------------------


def sync_payment_state(order):
    """
    Sets ``paid_in_full_at`` when the order's balance reaches 0.00 and
    clears it when a balance reappears or the order is cancelled
    (research R2). A COMPLETED order keeps its date: refunds after pickup
    are reported separately and do not reopen a balance (FR-028). The
    caller must hold the order's row lock. Saves only when the value
    changes.
    """
    if order.is_settled:
        return order

    fully_paid = (
        order.status != Status.CANCELLED and _net_paid(order) >= order.total_amount
    )

    if fully_paid and order.paid_in_full_at is None:
        order.paid_in_full_at = timezone.now()
    elif not fully_paid and order.paid_in_full_at is not None:
        order.paid_in_full_at = None
    else:
        return order

    order.save(update_fields=["paid_in_full_at", "updated_at"])
    return order


# ---------------------------------------------------------------------------
# Create and edit (US1)
# ---------------------------------------------------------------------------


@transaction.atomic
def create_stringing_order(
    *,
    user,
    racket_description,
    string_type,
    service_price,
    customer=None,
    tension="",
    notes="",
    discount_amount=ZERO,
    direct_cost=ZERO,
):
    """
    Creates a RECEIVED order with a new unique order number and writes a
    CREATED event. A zero-total order is immediately paid in full.
    """
    cleaned = _clean(
        {
            "racket_description": racket_description,
            "string_type": string_type,
            "tension": tension,
            "notes": notes,
            "service_price": service_price,
            "discount_amount": discount_amount,
            "direct_cost": direct_cost,
        }
    )
    _check_customer(customer)

    order = StringingOrder.objects.create(
        order_number=_next_order_number(),
        customer=customer,
        created_by=user,
        status=Status.RECEIVED,
        **cleaned,
    )
    _record_event(order, user, EventType.CREATED, to_status=Status.RECEIVED)
    return sync_payment_state(order)


@transaction.atomic
def update_stringing_order(*, order_id, user, **changes):
    """
    Edits customer, description, string, tension, notes and money fields
    of an order that is not COMPLETED or CANCELLED (FR-007). Refuses a new
    total below the amount already paid (FR-008). Writes an UPDATED event
    listing old and new values and updates ``paid_in_full_at``.
    """
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValidationError(f"Cannot edit: {', '.join(sorted(unknown))}.")

    order = _lock_order(order_id)

    if order.status in StringingOrder.FINAL_STATUSES:
        raise ValidationError(f"{Status(order.status).label} orders cannot be edited.")

    current = {field: getattr(order, field) for field in EDITABLE_FIELDS}
    cleaned = _clean({**current, **changes})

    diff = {
        field: [_audit_value(current[field]), _audit_value(cleaned[field])]
        for field in EDITABLE_FIELDS
        if cleaned[field] != current[field]
    }
    if not diff:
        return order

    if "customer" in diff and cleaned["customer"] is not None:
        _check_customer(cleaned["customer"])

    new_total = cleaned["service_price"] - cleaned["discount_amount"]
    paid = _net_paid(order)
    if new_total < paid:
        raise ValidationError(f"Total cannot be less than the {paid:.2f} already paid.")

    for field in diff:
        setattr(order, field, cleaned[field])
    order.save(update_fields=[*diff, "updated_at"])

    _record_event(order, user, EventType.UPDATED, changes=diff)
    return sync_payment_state(order)


# ---------------------------------------------------------------------------
# Status (US2)
# ---------------------------------------------------------------------------


@transaction.atomic
def change_status(*, order_id, user, to_status, expected_status=None):
    """
    Moves an order one step along the workflow (FR-011). COMPLETED requires
    a zero balance (FR-013). Maintains ``ready_at``/``completed_at`` and
    writes a STATUS_CHANGED event. Raises ``StatusConflict`` when
    ``expected_status`` no longer matches.
    """
    order = _lock_order(order_id)

    if expected_status and expected_status != order.status:
        raise StatusConflict(order.status)

    if to_status == Status.CANCELLED:
        raise ValidationError("Use cancel to cancel an order; a reason is required.")

    if to_status not in Status.values:
        raise ValidationError(f"Unknown status: {to_status}.")

    if order.status in StringingOrder.FINAL_STATUSES:
        raise ValidationError(
            f"{Status(order.status).label} orders cannot change status."
        )

    allowed = ALLOWED_TRANSITIONS[order.status]
    if to_status not in allowed:
        names = " or ".join(Status(s).label for s in allowed)
        raise ValidationError(
            f"A {Status(order.status).label} order can only move to {names}."
        )

    now = timezone.now()
    if to_status == Status.COMPLETED:
        balance = order.total_amount - _net_paid(order)
        if balance > 0:
            raise ValidationError(
                f"Balance of {balance:.2f} must be paid before pickup."
            )
        order.completed_at = now
    elif to_status == Status.READY:
        order.ready_at = now
    elif order.status == Status.READY:
        order.ready_at = None

    from_status = order.status
    order.status = to_status
    order.save(update_fields=["status", "ready_at", "completed_at", "updated_at"])

    _record_event(
        order,
        user,
        EventType.STATUS_CHANGED,
        from_status=from_status,
        to_status=to_status,
    )
    return order


# ---------------------------------------------------------------------------
# Cancellation (US5)
# ---------------------------------------------------------------------------


@transaction.atomic
def cancel_stringing_order(*, order_id, user, reason):
    """
    Cancels an order that is not COMPLETED or CANCELLED (FR-021). Payments
    are untouched; money received is returned afterwards with refunds
    (FR-023). Clears ``paid_in_full_at`` so the order leaves revenue
    (FR-027) and writes a CANCELLED event.
    """
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": ["A cancellation reason is required."]})

    order = _lock_order(order_id)

    if order.status in StringingOrder.FINAL_STATUSES:
        raise ValidationError(
            f"{Status(order.status).label} orders cannot be cancelled."
        )

    from_status = order.status
    order.status = Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancelled_by = user
    order.cancellation_reason = reason
    order.paid_in_full_at = None
    order.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "paid_in_full_at",
            "updated_at",
        ]
    )

    _record_event(
        order,
        user,
        EventType.CANCELLED,
        from_status=from_status,
        to_status=Status.CANCELLED,
        reason=reason,
    )
    return order


# ---------------------------------------------------------------------------
# Payments (US3)
# ---------------------------------------------------------------------------


@transaction.atomic
def record_order_payment(
    *,
    order_id,
    user,
    amount,
    payment_method,
    payment_type=Payment.PaymentType.RECEIPT,
    reference_number="",
    notes="",
    reason="",
):
    """
    Records a receipt or refund for a stringing order through the sales
    payment services, which lock the order, enforce balance limits and
    update ``paid_in_full_at``. Returns ``(payment, order)``.
    """
    # Imported here: sales.services imports this module.
    from sales.services import process_refund, record_payment

    order = StringingOrder.objects.get(pk=order_id)

    if payment_type == Payment.PaymentType.REFUND:
        # The refund's stored notes are its reason; keep any extra notes too.
        if reason and notes and notes.strip():
            reason = f"{reason.strip()} — {notes.strip()}"
        payment = process_refund(
            user=user,
            amount=amount,
            payment_method=payment_method,
            reason=reason,
            stringing_order=order,
            reference_number=reference_number,
        )
    else:
        payment = record_payment(
            user=user,
            amount=amount,
            payment_method=payment_method,
            stringing_order=order,
            reference_number=reference_number,
            notes=notes,
        )

    order.refresh_from_db()
    return payment, order
