"""
Customer domain services: every write to customers goes through here.

All functions raise ``django.core.exceptions.ValidationError`` for
business-rule violations (field errors are keyed by field name) and
``Customer.DoesNotExist`` for unknown ids.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from customers.models import Customer, CustomerAuditEvent
from customers.phone import PHONE_CHARACTERS

EDITABLE_FIELDS = ("full_name", "phone_number", "email", "address", "notes")
_TRIMMED_FIELDS = ("full_name", "phone_number", "email")


def _apply_and_validate(customer, fields):
    """
    Trims and assigns ``fields`` onto ``customer`` and validates them against
    the model's field rules (data-model.md Customer.*). Raises a
    field-keyed ValidationError without saving.
    """
    unknown = set(fields) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValidationError(
            {name: "This field cannot be changed here." for name in sorted(unknown)}
        )

    for name, value in fields.items():
        if value is None:
            value = ""
        if name in _TRIMMED_FIELDS:
            value = value.strip()
        setattr(customer, name, value)

    errors = {}
    try:
        customer.full_clean(
            exclude=[f for f in EDITABLE_FIELDS if f not in fields and customer.pk],
            validate_unique=False,
            validate_constraints=False,
        )
    except ValidationError as exc:
        errors.update(exc.message_dict)

    phone = customer.phone_number
    if phone and not PHONE_CHARACTERS.match(phone) and "phone_number" not in errors:
        errors["phone_number"] = [
            "Use only digits, spaces and + - ( ) in phone numbers."
        ]

    if errors:
        raise ValidationError(errors)


@transaction.atomic
def create_customer(**fields):
    """
    Creates an active customer.

    Side effects: inserts one Customer row. Duplicate phone numbers are
    allowed (callers warn with ``selectors.phone_matches``).
    """
    customer = Customer(is_active=True)
    fields.setdefault("full_name", "")
    _apply_and_validate(customer, fields)
    customer.save()
    return customer


@transaction.atomic
def update_customer(customer_id, **fields):
    """
    Updates any subset of a customer's editable fields (name, phone, email,
    address, notes). Archived customers can be edited; the archive status
    itself is changed only by ``archive_customer``/``reactivate_customer``.

    Side effects: updates one Customer row (and its normalized phone).
    Nothing is saved if any field is invalid.
    """
    customer = Customer.objects.select_for_update().get(pk=customer_id)
    _apply_and_validate(customer, fields)
    customer.save(update_fields=[*fields, "updated_at"])
    return customer


# ---------------------------------------------------------------------------
# Archive, reactivate, delete (US5)
# ---------------------------------------------------------------------------

HAS_HISTORY_MESSAGE = (
    "This customer has sales, stringing orders or pre-orders and cannot be "
    "deleted. Archive them instead."
)


def ensure_usable(customer):
    """
    Raises ValidationError if ``customer`` is archived (FR-017). ``None``
    (a walk-in) is always allowed. Call before attaching a customer to a
    new sale, stringing order or pre-order.
    """
    if customer is not None and not customer.is_active:
        raise ValidationError(
            f"{customer.full_name} is archived and cannot be used on new "
            "transactions."
        )


def _record(action, customer, user):
    CustomerAuditEvent.objects.create(
        action=action,
        customer_ref=customer.pk,
        customer_name=customer.full_name,
        performed_by=user,
    )


@transaction.atomic
def archive_customer(customer_id, user):
    """
    Archives an active customer. Their sales, stringing orders, pre-orders
    and payments are untouched (FR-016).

    Side effects: sets ``is_active`` to False and writes an ARCHIVED audit
    event.
    """
    customer = Customer.objects.select_for_update().get(pk=customer_id)

    if not customer.is_active:
        raise ValidationError("This customer is already archived.")

    customer.is_active = False
    customer.save(update_fields=["is_active", "updated_at"])
    _record(CustomerAuditEvent.Action.ARCHIVED, customer, user)

    return customer


@transaction.atomic
def reactivate_customer(customer_id, user):
    """
    Reactivates an archived customer.

    Side effects: sets ``is_active`` to True and writes a REACTIVATED audit
    event.
    """
    customer = Customer.objects.select_for_update().get(pk=customer_id)

    if customer.is_active:
        raise ValidationError("This customer is not archived.")

    customer.is_active = True
    customer.save(update_fields=["is_active", "updated_at"])
    _record(CustomerAuditEvent.Action.REACTIVATED, customer, user)

    return customer


def has_history(customer):
    """True if any sale (any status, drafts included), stringing order or
    pre-order references the customer."""
    return (
        customer.sales.exists()
        or customer.stringing_orders.exists()
        or customer.preorders.exists()
    )


@transaction.atomic
def delete_customer(customer_id, user):
    """
    Permanently deletes a customer who has no history (FR-019a). Customers
    with any sales, stringing orders or pre-orders are refused and must be
    archived instead (FR-019).

    The customer row is locked before checking, so a record attached at the
    same time either is seen here or fails its own foreign-key check
    (research R6). ``PROTECT`` foreign keys back this up.

    Side effects: writes a DELETED audit event (keeping the customer's id
    and name), then deletes the Customer row.
    """
    customer = Customer.objects.select_for_update().get(pk=customer_id)

    if has_history(customer):
        raise ValidationError(HAS_HISTORY_MESSAGE)

    _record(CustomerAuditEvent.Action.DELETED, customer, user)
    customer.delete()
