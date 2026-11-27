"""Product business rules (specs/005-ui-design research R6/R7).

Every function runs in one transaction and records a ``ProductEvent``. Stock is
only ever changed through ``inventory.services`` so it stays audited by
``InventoryMovement``.
"""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from inventory.services import adjust_stock, restock_product

from .models import Product, ProductEvent

VIEW_COST = "catalog.view_product_cost"
ADJUST_STOCK = "catalog.adjust_stock"

#: Fields an edit may change. ``stock_quantity`` is routed through inventory.
EDITABLE_FIELDS = (
    "sku",
    "name",
    "category",
    "subcategory",
    "brand",
    "model",
    "supplier",
    "variant_description",
    "description",
    "selling_price",
    "cost_price",
    "low_stock_threshold",
    "stock_quantity",
)
# ``is_active`` is deliberately absent: activation goes through deactivate/reactivate
# so it gets its own confirmation and DEACTIVATED/REACTIVATED event.
TRIMMED_FIELDS = (
    "sku",
    "name",
    "subcategory",
    "brand",
    "model",
    "supplier",
    "variant_description",
)
DECIMAL_FIELDS = ("selling_price", "cost_price")
INTEGER_FIELDS = ("low_stock_threshold", "stock_quantity")


DUPLICATE_SKU = {"sku": "A product with this SKU already exists."}


class ProductConflict(Exception):
    """A field being edited was changed by someone else since the editor loaded it."""

    def __init__(self, current):
        super().__init__("This product was changed by someone else.")
        self.current = current


def to_json_value(field, value):
    """Event/representation form of a value: Decimals as 2-place strings."""
    if field in DECIMAL_FIELDS and value is not None:
        return f"{Decimal(value):.2f}"
    return value


def _normalize(field, value):
    """Comparable form of a submitted or stored value; None if it can't be parsed."""
    try:
        if field in DECIMAL_FIELDS:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        if field in INTEGER_FIELDS:
            return int(value)
        return "" if value is None else str(value).strip()
    except (InvalidOperation, TypeError, ValueError):
        return None


def _require_reason(reason):
    if not reason or not reason.strip():
        raise ValidationError({"reason": "A reason is required."})
    return reason.strip()


def _trim(data):
    return {
        key: value.strip()
        if key in TRIMMED_FIELDS and isinstance(value, str)
        else value
        for key, value in data.items()
    }


@transaction.atomic
def create_product(*, user, data, initial_stock=0):
    """Creates a product with a CREATED event.

    Side effects: when ``initial_stock`` > 0, a RESTOCK movement ("Initial stock")
    raises stock in the same transaction. Requires ``catalog.view_product_cost`` to
    set ``cost_price`` (otherwise it defaults to 0).
    """
    if initial_stock is None:
        initial_stock = 0
    if initial_stock < 0:
        raise ValidationError({"initial_stock": "Starting stock cannot be negative."})
    data = _trim(data)
    if "cost_price" in data and not user.has_perm(VIEW_COST):
        raise PermissionDenied("You do not have permission to set product cost.")

    data.setdefault("cost_price", Decimal("0.00"))
    try:
        # Savepoint: a SKU taken since validation must surface as a 400, not a 500.
        with transaction.atomic():
            product = Product.objects.create(**data)
    except IntegrityError:
        raise ValidationError(DUPLICATE_SKU) from None
    ProductEvent.objects.create(
        product=product, action=ProductEvent.Action.CREATED, performed_by=user
    )
    if initial_stock > 0:
        restock_product(
            product_id=product.pk,
            quantity_received=initial_stock,
            created_by=user,
            reason="Initial stock",
        )
        product.refresh_from_db()
    return product


@transaction.atomic
def update_product(*, product_id, user, changes, expected, reason):
    """Applies an audited edit with a per-field conflict check.

    ``changes`` holds validated new values; ``expected`` the values the editor
    loaded for each changed field. Raises ``ProductConflict`` if any changed
    field no longer matches ``expected``.

    Side effects: locks the product row; writes one UPDATED event listing only
    fields whose value actually changes; a stock change writes an
    ADJUSTMENT_IN/OUT movement carrying ``reason``. Changing stock requires
    ``catalog.adjust_stock``; changing cost requires ``catalog.view_product_cost``.
    """
    reason = _require_reason(reason)
    if not changes:
        raise ValidationError({"changes": "Change at least one field."})
    unknown = sorted(set(changes) - set(EDITABLE_FIELDS))
    if unknown:
        raise ValidationError(
            {"changes": f"These fields cannot be edited: {', '.join(unknown)}."}
        )
    missing = sorted(set(changes) - set(expected))
    if missing:
        raise ValidationError(
            {"expected": f"Original values are required for: {', '.join(missing)}."}
        )
    if "stock_quantity" in changes and not user.has_perm(ADJUST_STOCK):
        raise PermissionDenied("You do not have permission to change stock.")
    if "cost_price" in changes and not user.has_perm(VIEW_COST):
        raise PermissionDenied("You do not have permission to change product cost.")

    product = Product.objects.select_for_update().get(pk=product_id)
    changes = _trim(changes)

    conflicts = {
        field: to_json_value(field, getattr(product, field))
        for field in changes
        if _normalize(field, getattr(product, field))
        != _normalize(field, expected[field])
    }
    if conflicts:
        raise ProductConflict(conflicts)

    diff = {
        field: [
            to_json_value(field, getattr(product, field)),
            to_json_value(field, value),
        ]
        for field, value in changes.items()
        if _normalize(field, getattr(product, field)) != _normalize(field, value)
    }
    if not diff:
        raise ValidationError({"changes": "Nothing changed."})

    event_changes = dict(diff)
    if "stock_quantity" in diff:
        old_stock, new_stock = diff["stock_quantity"]
        movement = adjust_stock(
            product_id=product.pk,
            quantity_change=new_stock - old_stock,
            reason=reason,
            created_by=user,
        )
        event_changes["movement_id"] = movement.pk

    field_updates = {f: changes[f] for f in diff if f != "stock_quantity"}
    if field_updates:
        for field, value in field_updates.items():
            setattr(product, field, value)
        try:
            with transaction.atomic():
                product.save(update_fields=[*field_updates, "updated_at"])
        except IntegrityError:
            raise ValidationError(DUPLICATE_SKU) from None

    ProductEvent.objects.create(
        product=product,
        action=ProductEvent.Action.UPDATED,
        changes=event_changes,
        reason=reason,
        performed_by=user,
    )
    return Product.objects.get(pk=product.pk)


def _set_active(*, product_id, user, reason, active):
    reason = _require_reason(reason)
    product = Product.objects.select_for_update().get(pk=product_id)
    if product.is_active == active:
        state = "active" if active else "inactive"
        raise ValidationError(f"Product is already {state}.")
    product.is_active = active
    product.save(update_fields=["is_active", "updated_at"])
    ProductEvent.objects.create(
        product=product,
        action=ProductEvent.Action.REACTIVATED
        if active
        else ProductEvent.Action.DEACTIVATED,
        reason=reason,
        performed_by=user,
    )
    return product


@transaction.atomic
def deactivate_product(*, product_id, user, reason):
    """Hides a product from sale; never deletes it. Side effects: DEACTIVATED event."""
    return _set_active(product_id=product_id, user=user, reason=reason, active=False)


@transaction.atomic
def reactivate_product(*, product_id, user, reason):
    """Makes an inactive product sellable again. Side effects: REACTIVATED event."""
    return _set_active(product_id=product_id, user=user, reason=reason, active=True)
