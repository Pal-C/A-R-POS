"""
Pre-order domain services (spec 003).

Lifecycle:

    PENDING ⇄ ORDERED ⇄ ARRIVED ──fulfill (balance 0)──▶ FULFILLED
       └─────────┴─────────┴──cancel(reason)──▶ CANCELLED

- Moves are one step at a time; FULFILLED and CANCELLED are final.
- ORDERED → ARRIVED also happens in bulk via ``mark_product_arrived``.
- Money is recorded only as ``sales.Payment`` rows through
  ``sales.services.record_payment`` / ``process_refund``.
- Pre-orders never change product stock (spec Q1).
- Every change writes an append-only ``PreOrderEvent``.

All functions raise ``django.core.exceptions.ValidationError`` for
business-rule violations, ``PermissionDenied`` for a price override without
permission, and ``DoesNotExist`` for unknown ids.
"""

from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from catalog.models import Product
from customers.services import ensure_usable
from preorders.models import PreOrder, PreOrderEvent
from preorders.selectors import store_today
from sales.models import Payment
from sales.selectors import net_paid_expression

Status = PreOrder.Status
EventType = PreOrderEvent.EventType

ALLOWED_TRANSITIONS = {
    Status.PENDING: (Status.ORDERED,),
    Status.ORDERED: (Status.ARRIVED, Status.PENDING),
    Status.ARRIVED: (Status.ORDERED,),
}

EDITABLE_BY_STATUS = {
    Status.PENDING: ("quantity", "agreed_unit_price", "expected_arrival_date", "notes"),
    Status.ORDERED: ("quantity", "agreed_unit_price", "expected_arrival_date", "notes"),
    Status.ARRIVED: ("expected_arrival_date", "notes"),
}
EDITABLE_FIELDS = EDITABLE_BY_STATUS[Status.PENDING]


class StatusConflict(ValidationError):
    """The pre-order's status changed since the client last read it."""

    def __init__(self, current_status):
        self.current_status = current_status
        super().__init__(
            "This pre-order's status was changed by someone else. "
            f"It is now {Status(current_status).label}."
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _next_order_number():
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('preorder_number_seq')")
        (number,) = cursor.fetchone()
    return f"PO-{store_today().year}-{number:06d}"


def _lock_preorder(preorder_id):
    return PreOrder.objects.select_for_update().get(pk=preorder_id)


def _net_paid(preorder):
    return Payment.objects.filter(preorder=preorder).aggregate(
        net=net_paid_expression()
    )["net"]


def _record_event(preorder, user, event_type, **fields):
    return PreOrderEvent.objects.create(
        preorder=preorder, performed_by=user, event_type=event_type, **fields
    )


def _audit_value(value):
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, date):
        return value.isoformat()
    return value


def _field_errors(*, quantity=None, price=None, check_quantity=True, check_price=True):
    errors = {}
    if check_quantity and (quantity is None or quantity < 1):
        errors["quantity"] = ["Quantity must be at least 1."]
    if check_price and (price is None or price < 0):
        errors["agreed_unit_price"] = ["Price must be zero or more."]
    return errors


def _check_arrival_date(value, errors):
    if value is not None and value < store_today():
        errors["expected_arrival_date"] = [
            "Expected arrival date cannot be in the past."
        ]


# ---------------------------------------------------------------------------
# Create and edit (US1)
# ---------------------------------------------------------------------------


@transaction.atomic
def create_preorder(
    *,
    user,
    customer,
    product,
    quantity,
    agreed_unit_price=None,
    expected_arrival_date=None,
    notes="",
):
    """
    Creates a PENDING pre-order with a new unique order number and writes a
    CREATED event. The agreed price defaults to the product's current
    selling price. Does not touch stock.
    """
    if agreed_unit_price is None and product is not None:
        agreed_unit_price = product.selling_price

    errors = _field_errors(quantity=quantity, price=agreed_unit_price)
    _check_arrival_date(expected_arrival_date, errors)

    if customer is None:
        errors["customer"] = ["A customer is required."]
    elif not customer.is_active:
        try:
            ensure_usable(customer)
        except ValidationError as exc:
            errors["customer"] = exc.messages

    if product is None:
        errors["product"] = ["A product is required."]
    elif not product.is_active:
        errors["product"] = [f"{product.name} is inactive and cannot be pre-ordered."]

    if errors:
        raise ValidationError(errors)

    preorder = PreOrder.objects.create(
        order_number=_next_order_number(),
        customer=customer,
        product=product,
        quantity=quantity,
        agreed_unit_price=agreed_unit_price,
        expected_arrival_date=expected_arrival_date,
        notes=(notes or "").strip(),
        created_by=user,
        status=Status.PENDING,
    )
    _record_event(preorder, user, EventType.CREATED, to_status=Status.PENDING)
    return preorder


@transaction.atomic
def update_preorder(*, preorder_id, user, can_override_price=False, **changes):
    """
    Edits quantity, agreed price, expected arrival date and notes, as the
    current status allows (research R5). Refuses a new total below the
    amount paid, and a price change after payment without
    ``can_override_price`` (PermissionDenied). Writes an UPDATED event.
    """
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValidationError(f"Cannot edit: {', '.join(sorted(unknown))}.")

    preorder = _lock_preorder(preorder_id)

    if preorder.status in PreOrder.FINAL_STATUSES:
        raise ValidationError(
            f"{Status(preorder.status).label} pre-orders cannot be edited."
        )

    if "notes" in changes:
        changes["notes"] = (changes["notes"] or "").strip()

    diff = {
        field: [getattr(preorder, field), value]
        for field, value in changes.items()
        if getattr(preorder, field) != value
    }
    if not diff:
        return preorder

    allowed = EDITABLE_BY_STATUS[preorder.status]
    locked = [field for field in diff if field not in allowed]
    if locked:
        raise ValidationError(
            {
                field: [
                    f"Cannot be changed once the pre-order is "
                    f"{Status(preorder.status).label}."
                ]
                for field in locked
            }
        )

    quantity = changes.get("quantity", preorder.quantity)
    price = changes.get("agreed_unit_price", preorder.agreed_unit_price)
    errors = _field_errors(
        quantity=quantity,
        price=price,
        check_quantity="quantity" in diff,
        check_price="agreed_unit_price" in diff,
    )
    if "expected_arrival_date" in diff:
        _check_arrival_date(changes["expected_arrival_date"], errors)
    if errors:
        raise ValidationError(errors)

    paid = _net_paid(preorder)
    if "agreed_unit_price" in diff and paid > 0 and not can_override_price:
        raise PermissionDenied(
            "You do not have permission to change the agreed price after a payment."
        )

    if quantity * price < paid:
        raise ValidationError(f"Total cannot be less than the {paid:.2f} already paid.")

    for field in diff:
        setattr(preorder, field, changes[field])
    preorder.save(update_fields=[*diff, "updated_at"])

    _record_event(
        preorder,
        user,
        EventType.UPDATED,
        changes={
            field: [_audit_value(old), _audit_value(new)]
            for field, (old, new) in diff.items()
        },
    )
    return preorder


# ---------------------------------------------------------------------------
# Status and arrival (US3)
# ---------------------------------------------------------------------------


def _apply_transition(preorder, user, to_status, *, extra=None):
    """Sets the new status and its timestamp and writes a STATUS_CHANGED event."""
    now = timezone.now()
    from_status = preorder.status

    if to_status == Status.ORDERED and from_status == Status.PENDING:
        preorder.ordered_at = now
    elif to_status == Status.PENDING:
        preorder.ordered_at = None
    elif to_status == Status.ARRIVED:
        preorder.arrived_at = now
    elif to_status == Status.ORDERED and from_status == Status.ARRIVED:
        preorder.arrived_at = None

    preorder.status = to_status
    preorder.save(update_fields=["status", "ordered_at", "arrived_at", "updated_at"])
    _record_event(
        preorder,
        user,
        EventType.STATUS_CHANGED,
        from_status=from_status,
        to_status=to_status,
        extra=extra or {},
    )


@transaction.atomic
def change_status(*, preorder_id, user, to_status, expected_status=None):
    """
    Moves one pre-order a single step (FR-008). FULFILLED and CANCELLED
    have their own services. Maintains ``ordered_at``/``arrived_at`` and
    writes a STATUS_CHANGED event. Raises ``StatusConflict`` when
    ``expected_status`` no longer matches.
    """
    preorder = _lock_preorder(preorder_id)

    if expected_status and expected_status != preorder.status:
        raise StatusConflict(preorder.status)

    if to_status == Status.FULFILLED:
        raise ValidationError("Use fulfill to hand over a pre-order.")
    if to_status == Status.CANCELLED:
        raise ValidationError("Use cancel to cancel a pre-order; a reason is required.")
    if to_status not in Status.values:
        raise ValidationError(f"Unknown status: {to_status}.")

    if preorder.status in PreOrder.FINAL_STATUSES:
        raise ValidationError(
            f"{Status(preorder.status).label} pre-orders cannot change status."
        )

    allowed = ALLOWED_TRANSITIONS[preorder.status]
    if to_status not in allowed:
        names = " or ".join(Status(s).label for s in allowed)
        raise ValidationError(
            f"A {Status(preorder.status).label} pre-order can only move to {names}."
        )

    _apply_transition(preorder, user, to_status)
    return preorder


@transaction.atomic
def mark_product_arrived(*, product_id, received_quantity, user, preorder_ids=None):
    """
    Marks a product's ORDERED pre-orders as ARRIVED for a delivery of
    ``received_quantity`` units (FR-009, research R4).

    - Default: oldest first, skipping orders whose full quantity no longer
      fits in the remaining units.
    - With ``preorder_ids``: exactly those orders, which must be ORDERED
      pre-orders of this product whose quantities fit; otherwise nothing
      changes.

    Locks the product's ORDERED rows in primary-key order. Does not touch
    stock. Returns ``{"marked": [PreOrder], "units_used", "units_left"}``.
    """
    product = Product.objects.get(pk=product_id)

    if received_quantity is None or received_quantity < 1:
        raise ValidationError({"received_quantity": ["Enter at least 1 unit."]})

    waiting = list(
        PreOrder.objects.select_for_update()
        .filter(product=product, status=Status.ORDERED)
        .order_by("pk")
    )

    if preorder_ids is not None:
        wanted = set(preorder_ids)
        if not wanted:
            raise ValidationError({"preorder_ids": ["Choose at least one pre-order."]})
        selected = [order for order in waiting if order.pk in wanted]
        missing = sorted(wanted - {order.pk for order in selected})
        if missing:
            raise ValidationError(
                {
                    "preorder_ids": [
                        "Not Ordered pre-orders of this product: "
                        + ", ".join(str(pk) for pk in missing)
                        + "."
                    ]
                }
            )
        units = sum(order.quantity for order in selected)
        if units > received_quantity:
            raise ValidationError(
                {
                    "preorder_ids": [
                        f"The selected pre-orders need {units} units but only "
                        f"{received_quantity} arrived."
                    ]
                }
            )
        to_mark = sorted(selected, key=lambda order: (order.created_at, order.pk))
    else:
        to_mark = []
        remaining = received_quantity
        for order in sorted(waiting, key=lambda o: (o.created_at, o.pk)):
            if order.quantity <= remaining:
                to_mark.append(order)
                remaining -= order.quantity

    extra = {"arrival": {"received_quantity": received_quantity}}
    for order in to_mark:
        _apply_transition(order, user, Status.ARRIVED, extra=extra)

    units_used = sum(order.quantity for order in to_mark)
    return {
        "marked": to_mark,
        "units_used": units_used,
        "units_left": received_quantity - units_used,
    }


# ---------------------------------------------------------------------------
# Fulfillment (US4)
# ---------------------------------------------------------------------------


@transaction.atomic
def fulfill_preorder(*, preorder_id, user):
    """
    Hands over an ARRIVED pre-order whose balance is 0.00 (FR-016).
    Records ``fulfilled_at``/``fulfilled_by``, marks it settled, and writes
    a STATUS_CHANGED event. Does not touch stock.
    """
    preorder = _lock_preorder(preorder_id)

    if preorder.status in PreOrder.FINAL_STATUSES:
        raise ValidationError(
            f"{Status(preorder.status).label} pre-orders cannot be fulfilled."
        )
    if preorder.status != Status.ARRIVED:
        raise ValidationError("The goods have not arrived yet.")

    balance = preorder.total_amount - _net_paid(preorder)
    if balance > 0:
        raise ValidationError(f"Balance of {balance:.2f} must be paid before handover.")

    from_status = preorder.status
    preorder.status = Status.FULFILLED
    preorder.fulfilled_at = timezone.now()
    preorder.fulfilled_by = user
    # Fulfillment requires full payment, so the pre-order is settled now.
    preorder.settled_at = preorder.fulfilled_at
    preorder.save(
        update_fields=[
            "status",
            "fulfilled_at",
            "fulfilled_by",
            "settled_at",
            "updated_at",
        ]
    )

    _record_event(
        preorder,
        user,
        EventType.STATUS_CHANGED,
        from_status=from_status,
        to_status=Status.FULFILLED,
    )
    return preorder


def sync_settlement(preorder):
    """
    Marks a legacy fulfilled pre-order settled once its balance is paid
    (research R2). Pre-orders fulfilled through ``fulfill_preorder`` are
    settled already. The caller must hold the pre-order's row lock.
    """
    if preorder.status != Status.FULFILLED or preorder.settled_at is not None:
        return preorder
    if _net_paid(preorder) >= preorder.total_amount:
        preorder.settled_at = timezone.now()
        preorder.save(update_fields=["settled_at", "updated_at"])
    return preorder


# ---------------------------------------------------------------------------
# Cancellation (US6)
# ---------------------------------------------------------------------------


@transaction.atomic
def cancel_preorder(*, preorder_id, user, reason):
    """
    Cancels a pre-order that is not FULFILLED or CANCELLED (FR-022).
    Payments are untouched; money received is returned afterwards with
    refunds (FR-023). Writes a CANCELLED event.
    """
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": ["A cancellation reason is required."]})

    preorder = _lock_preorder(preorder_id)

    if preorder.status in PreOrder.FINAL_STATUSES:
        raise ValidationError(
            f"{Status(preorder.status).label} pre-orders cannot be cancelled."
        )

    from_status = preorder.status
    preorder.status = Status.CANCELLED
    preorder.cancelled_at = timezone.now()
    preorder.cancelled_by = user
    preorder.cancellation_reason = reason
    preorder.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "updated_at",
        ]
    )

    _record_event(
        preorder,
        user,
        EventType.CANCELLED,
        from_status=from_status,
        to_status=Status.CANCELLED,
        reason=reason,
    )
    return preorder


# ---------------------------------------------------------------------------
# Payments (US2)
# ---------------------------------------------------------------------------


@transaction.atomic
def record_preorder_payment(
    *,
    preorder_id,
    user,
    amount,
    payment_method,
    payment_type=Payment.PaymentType.RECEIPT,
    reference_number="",
    notes="",
    reason="",
):
    """
    Records a receipt or refund for a pre-order through the sales payment
    services, which lock the pre-order and enforce balance limits.
    Receipts are refused on FULFILLED and CANCELLED pre-orders. Returns
    ``(payment, preorder)``.
    """
    # Imported here: sales.services imports preorders.models.
    from sales.services import process_refund, record_payment

    preorder = PreOrder.objects.get(pk=preorder_id)

    if payment_type == Payment.PaymentType.REFUND:
        # The refund's stored notes are its reason; keep any extra notes too.
        if reason and notes and notes.strip():
            reason = f"{reason.strip()} — {notes.strip()}"
        payment = process_refund(
            user=user,
            amount=amount,
            payment_method=payment_method,
            reason=reason,
            preorder=preorder,
            reference_number=reference_number,
        )
    else:
        payment = record_payment(
            user=user,
            amount=amount,
            payment_method=payment_method,
            preorder=preorder,
            reference_number=reference_number,
            notes=notes,
        )

    preorder.refresh_from_db()
    return payment, preorder
