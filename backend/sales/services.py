"""
Sales domain services.

Lifecycle of a sale:

    DRAFT ──finalize──▶ PENDING_PAYMENT ◀──payments/refunds──▶ COMPLETED
      │                       │                                   │
      └─(edit items/discount) └──────────────cancel───────────────┘──▶ CANCELLED

- Drafts hold price/cost snapshots but do not touch inventory.
- Finalizing deducts inventory (one SALE movement per line) and assigns
  a sale number.
- Payments (receipts and refunds) move the sale between PENDING_PAYMENT
  and COMPLETED based on the net amount received.
- Cancelling a finalized sale reverses its SALE movements. Money already
  received is returned with refunds, which remain allowed after
  cancellation.

All functions raise ``django.core.exceptions.ValidationError`` for
business-rule violations and ``Sale.DoesNotExist`` / ``SaleItem.DoesNotExist``
for unknown ids.
"""

from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.models import Product
from customers.services import ensure_usable
from inventory.models import InventoryMovement
from inventory.services import (
    deduct_stock_for_sale,
    reverse_movement,
)
from preorders.models import PreOrder
from preorders.services import sync_settlement as sync_preorder_settlement
from sales.models import Payment, Sale, SaleEvent, SaleItem
from stringing.models import StringingOrder
from stringing.services import sync_payment_state

ZERO = Decimal("0.00")

# Sentinel for "argument not supplied" where None is a meaningful value.
_UNSET = object()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def store_today():
    """Today's date in the store's time zone (business dates; storage stays UTC)."""
    return timezone.now().astimezone(ZoneInfo(settings.STORE_TIME_ZONE)).date()


def _sale_reference(sale):
    return sale.sale_number or str(sale.pk)


def _lock_draft_sale(sale_id):
    """Locks a sale row and verifies it is still a draft."""
    sale = Sale.objects.select_for_update().get(pk=sale_id)

    if sale.status != Sale.Status.DRAFT:
        raise ValidationError("Only draft sales can be modified.")

    return sale


def _validate_line(*, product, quantity, discount_amount, unit_price):
    """Validates one sale line against a unit price snapshot."""
    if not product.is_active:
        raise ValidationError(f"{product.name} is inactive and cannot be sold.")

    if quantity is None or quantity <= 0:
        raise ValidationError(f"Quantity for {product.name} must be greater than zero.")

    if discount_amount < 0:
        raise ValidationError("Item discount cannot be negative.")

    if discount_amount > unit_price * quantity:
        raise ValidationError(f"Discount for {product.name} exceeds its line subtotal.")


def _recalculate_totals(sale):
    """
    Recomputes subtotal and total from the sale's saved line snapshots
    and saves them. Raises if the sale-level discount no longer fits.

    Returns the item discount total.
    """
    subtotal = ZERO
    item_discounts = ZERO

    for item in sale.items.all():
        subtotal += item.line_subtotal
        item_discounts += item.discount_amount

    if sale.discount_amount < 0:
        raise ValidationError("Sale discount cannot be negative.")

    if sale.discount_amount > subtotal - item_discounts:
        raise ValidationError("Sale discount exceeds the remaining sale amount.")

    sale.subtotal = subtotal
    sale.total_amount = subtotal - item_discounts - sale.discount_amount

    sale.save(
        update_fields=[
            "subtotal",
            "discount_amount",
            "total_amount",
            "customer",
            "updated_at",
        ]
    )

    return item_discounts


def _net_received(payments):
    return (
        sum(
            (
                payment.amount
                if payment.payment_type == Payment.PaymentType.RECEIPT
                else -payment.amount
            )
            for payment in payments
        )
        or ZERO
    )


# ---------------------------------------------------------------------------
# Draft sales
# ---------------------------------------------------------------------------


@transaction.atomic
def create_draft_sale(
    *,
    user,
    items,
    customer=None,
    discount_amount=ZERO,
):
    """
    Creates a draft sale with one line per product.

    Each line snapshots the product's current selling and cost price.
    Does not deduct inventory; that happens on finalization.

    ``items`` is a list of dicts: ``{"product", "quantity",
    "discount_amount" (optional)}``.
    """

    if not items:
        raise ValidationError("A sale must contain at least one item.")

    if discount_amount < 0:
        raise ValidationError("Sale discount cannot be negative.")

    ensure_usable(customer)

    product_ids = [item["product"].pk for item in items]

    if len(product_ids) != len(set(product_ids)):
        raise ValidationError("Duplicate products are not allowed.")

    # Lock products in a consistent order to reduce the chance
    # of deadlocks when multiple sales are created simultaneously.
    products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=product_ids)
        .order_by("pk")
    }

    if len(products) != len(product_ids):
        raise ValidationError("One or more selected products do not exist.")

    sale = Sale.objects.create(
        customer=customer,
        created_by=user,
        status=Sale.Status.DRAFT,
    )
    # Applied after the lines exist: the database requires
    # discount_amount <= subtotal, and subtotal starts at zero.
    sale.discount_amount = discount_amount

    for item_data in items:
        product = products[item_data["product"].pk]
        quantity = item_data["quantity"]
        item_discount = item_data.get("discount_amount", ZERO)

        _validate_line(
            product=product,
            quantity=quantity,
            discount_amount=item_discount,
            unit_price=product.selling_price,
        )

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_selling_price=product.selling_price,
            unit_cost_price=product.cost_price,
            discount_amount=item_discount,
        )

    _recalculate_totals(sale)

    return sale


@transaction.atomic
def update_draft_sale(*, sale_id, customer=_UNSET, discount_amount=_UNSET):
    """
    Changes the customer and/or sale-level discount of a draft sale.

    Pass ``customer=None`` to make it a walk-in sale. Omitted arguments
    are left unchanged.
    """
    sale = _lock_draft_sale(sale_id)

    if customer is not _UNSET:
        ensure_usable(customer)
        sale.customer = customer

    if discount_amount is not _UNSET:
        sale.discount_amount = discount_amount

    _recalculate_totals(sale)

    return sale


@transaction.atomic
def add_sale_item(*, sale_id, product, quantity, discount_amount=ZERO):
    """
    Adds a product to a draft sale.

    If the product is already on the sale, the quantity and discount are
    added to the existing line, which keeps its original price snapshot.
    Otherwise a new line is created with the product's current prices.

    Returns the created or updated SaleItem.
    """
    sale = _lock_draft_sale(sale_id)
    product = Product.objects.select_for_update().get(pk=product.pk)

    item = sale.items.filter(product=product).first()

    if item is None:
        _validate_line(
            product=product,
            quantity=quantity,
            discount_amount=discount_amount,
            unit_price=product.selling_price,
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_selling_price=product.selling_price,
            unit_cost_price=product.cost_price,
            discount_amount=discount_amount,
        )
    else:
        if quantity is None or quantity <= 0:
            raise ValidationError(
                f"Quantity for {product.name} must be greater than zero."
            )
        new_quantity = item.quantity + quantity
        new_discount = item.discount_amount + discount_amount
        _validate_line(
            product=product,
            quantity=new_quantity,
            discount_amount=new_discount,
            unit_price=item.unit_selling_price,
        )
        item.quantity = new_quantity
        item.discount_amount = new_discount
        item.save(update_fields=["quantity", "discount_amount"])

    _recalculate_totals(sale)

    return item


@transaction.atomic
def update_sale_item(*, sale_id, item_id, quantity=None, discount_amount=None):
    """
    Sets the quantity and/or discount of a line on a draft sale.
    The line's price snapshot is not changed.
    """
    sale = _lock_draft_sale(sale_id)
    item = sale.items.select_related("product").get(pk=item_id)

    new_quantity = item.quantity if quantity is None else quantity
    new_discount = item.discount_amount if discount_amount is None else discount_amount

    _validate_line(
        product=item.product,
        quantity=new_quantity,
        discount_amount=new_discount,
        unit_price=item.unit_selling_price,
    )

    item.quantity = new_quantity
    item.discount_amount = new_discount
    item.save(update_fields=["quantity", "discount_amount"])

    _recalculate_totals(sale)

    return item


@transaction.atomic
def remove_sale_item(*, sale_id, item_id):
    """
    Removes a line from a draft sale. A draft may become empty, but it
    cannot be finalized until it has at least one item.
    """
    sale = _lock_draft_sale(sale_id)
    item = sale.items.get(pk=item_id)
    item.delete()

    _recalculate_totals(sale)

    return sale


# ---------------------------------------------------------------------------
# Finalization
# ---------------------------------------------------------------------------


@transaction.atomic
def finalize_sale(sale_id, user):
    """
    Finalizes a draft sale: recalculates totals from the line snapshots,
    deducts inventory for every line, assigns a sale number, and moves
    the sale to PENDING_PAYMENT (or COMPLETED for a zero-total sale).

    Fails without side effects if any product is inactive or out of stock,
    or if the sale's customer has been archived.
    """
    # Lock only the sale row; the customer is joined in for the archive check.
    sale = (
        Sale.objects.select_for_update(of=("self",))
        .select_related("customer")
        .get(pk=sale_id)
    )

    if sale.status != Sale.Status.DRAFT:
        raise ValidationError("Only draft sales can be finalized.")

    ensure_usable(sale.customer)

    items = list(sale.items.select_related("product").order_by("product_id"))

    if not items:
        raise ValidationError("Cannot finalize a sale without items.")

    for item in items:
        if not item.product.is_active:
            raise ValidationError(
                f"{item.product.name} is inactive and cannot be sold."
            )

    _recalculate_totals(sale)

    finalized_at = timezone.now()
    sale.sale_number = f"S{finalized_at:%Y%m%d}-{sale.pk:06d}"

    # Deduct inventory in a consistent product order.
    for item in items:
        deduct_stock_for_sale(
            product_id=item.product_id,
            quantity_sold=item.quantity,
            created_by=user,
            sale_item=item,
            reference_number=sale.sale_number,
        )

    sale.finalized_at = finalized_at
    if sale.sale_date is None:
        sale.sale_date = store_today()
    sale.status = (
        Sale.Status.COMPLETED if sale.total_amount == 0 else Sale.Status.PENDING_PAYMENT
    )

    sale.save(
        update_fields=[
            "sale_number",
            "finalized_at",
            "sale_date",
            "status",
            "updated_at",
        ]
    )

    return sale


# ---------------------------------------------------------------------------
# Payments and refunds
# ---------------------------------------------------------------------------


@transaction.atomic
def record_payment(
    *,
    user,
    amount,
    payment_method,
    payment_type=Payment.PaymentType.RECEIPT,
    sale=None,
    stringing_order=None,
    preorder=None,
    reference_number="",
    notes="",
):
    """
    Records money received (RECEIPT) or returned (REFUND) for exactly one
    sale, stringing order, or pre-order.

    - Receipts cannot exceed the outstanding balance and are not allowed
      on drafts, cancelled orders, settled stringing orders or fulfilled
      pre-orders.
    - Refunds cannot exceed the net amount received.
    - For sales, the status is set to COMPLETED when fully paid and back
      to PENDING_PAYMENT otherwise (cancelled sales stay cancelled).
    - For stringing orders, ``paid_in_full_at`` is set or cleared via
      ``stringing.services.sync_payment_state``.
    """
    targets = [sale, stringing_order, preorder]

    if sum(target is not None for target in targets) != 1:
        raise ValidationError("A payment must belong to exactly one order.")

    if amount is None or amount <= 0:
        raise ValidationError("Payment amount must be positive.")

    if payment_type not in Payment.PaymentType.values:
        raise ValidationError("Invalid payment type.")

    if payment_method not in Payment.Method.values:
        raise ValidationError("Invalid payment method.")

    is_receipt = payment_type == Payment.PaymentType.RECEIPT

    if sale is not None:
        order = Sale.objects.select_for_update().get(pk=sale.pk)
        target_field = "sale"

        if order.status == Sale.Status.DRAFT:
            raise ValidationError("Payments can only be recorded for finalized sales.")

        if order.status == Sale.Status.CANCELLED and is_receipt:
            raise ValidationError("Cannot receive payment for a cancelled sale.")

    elif stringing_order is not None:
        order = StringingOrder.objects.select_for_update().get(pk=stringing_order.pk)
        target_field = "stringing_order"

        if order.status == StringingOrder.Status.CANCELLED and is_receipt:
            raise ValidationError(
                "Cannot receive payment for a cancelled stringing order."
            )

        # A completed, fully paid order is settled; money after pickup is
        # only ever returned (stringing FR-028).
        if order.is_settled and is_receipt:
            raise ValidationError(
                "This stringing order is completed and settled; it cannot "
                "receive more payments."
            )

    else:
        order = PreOrder.objects.select_for_update().get(pk=preorder.pk)
        target_field = "preorder"

        if order.status == PreOrder.Status.CANCELLED and is_receipt:
            raise ValidationError("Cannot receive payment for a cancelled pre-order.")

        # Fulfilled pre-orders are settled; money after handover is only
        # ever returned (pre-orders research R2).
        if order.is_settled and is_receipt:
            raise ValidationError(
                "This pre-order has been fulfilled; it cannot receive more payments."
            )

    received = _net_received(
        Payment.objects.filter(
            **{target_field: order},
            status=Payment.Status.POSTED,
        )
    )

    if is_receipt:
        if received + amount > order.total_amount:
            raise ValidationError("Payment exceeds the outstanding balance.")
    elif amount > received:
        raise ValidationError("Refund cannot exceed the net amount received.")

    payment = Payment.objects.create(
        **{target_field: order},
        amount=amount,
        payment_method=payment_method,
        payment_type=payment_type,
        status=Payment.Status.POSTED,
        received_by=user,
        reference_number=reference_number,
        notes=notes,
    )

    # Stringing orders track the date they became paid in full (revenue
    # recognition, stringing research R2); the order is still locked here.
    if target_field == "stringing_order":
        sync_payment_state(order)

    # Legacy fulfilled pre-orders become settled once paid in full.
    if target_field == "preorder":
        sync_preorder_settlement(order)

    # Sale status reflects the net amount received.
    if target_field == "sale" and order.status != Sale.Status.CANCELLED:
        updated_received = received + amount if is_receipt else received - amount

        order.status = (
            Sale.Status.COMPLETED
            if updated_received >= order.total_amount
            else Sale.Status.PENDING_PAYMENT
        )
        order.save(update_fields=["status", "updated_at"])

    return payment


def process_refund(
    *,
    user,
    amount,
    payment_method,
    reason,
    sale=None,
    stringing_order=None,
    preorder=None,
    reference_number="",
):
    """
    Returns money to the customer. A reason is required and is stored as
    the refund's notes.

    Refunds only move money; they do not change inventory. To put stock
    back, cancel the sale (which reverses its inventory deductions).
    """
    if not reason or not reason.strip():
        raise ValidationError("A reason is required for refunds.")

    return record_payment(
        user=user,
        amount=amount,
        payment_method=payment_method,
        payment_type=Payment.PaymentType.REFUND,
        sale=sale,
        stringing_order=stringing_order,
        preorder=preorder,
        reference_number=reference_number,
        notes=reason.strip(),
    )


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


@transaction.atomic
def cancel_sale(*, sale_id, user, reason):
    """
    Cancels a finalized sale (PENDING_PAYMENT or COMPLETED) and reverses
    every inventory deduction it made. Payments are left untouched; any
    money received is returned with ``process_refund`` (see
    ``Sale.refund_due``).
    """
    if not reason or not reason.strip():
        raise ValidationError("A cancellation reason is required.")

    sale = Sale.objects.select_for_update().get(pk=sale_id)

    if sale.status == Sale.Status.DRAFT:
        raise ValidationError("Draft sales cannot be cancelled through this operation.")

    if sale.status == Sale.Status.CANCELLED:
        raise ValidationError("This sale has already been cancelled.")

    reference = _sale_reference(sale)

    movements = InventoryMovement.objects.filter(
        sale_item__sale=sale,
        movement_type=InventoryMovement.MovementType.SALE,
        reversals__isnull=True,
    ).order_by("product_id", "pk")

    for movement in movements:
        reverse_movement(
            movement_id=movement.pk,
            created_by=user,
            reason=f"Cancellation of sale {reference}: {reason.strip()}",
            reference_number=reference,
        )

    sale.status = Sale.Status.CANCELLED
    sale.cancelled_at = timezone.now()
    sale.cancelled_by = user
    sale.cancellation_reason = reason.strip()

    sale.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "updated_at",
        ]
    )

    return sale


BACKDATE_PERMISSION = "sales.backdate_sale"
RECORD_PAYMENT_PERMISSION = "sales.record_payment"


def _check_cart(items, discount_amount):
    if not items:
        raise ValidationError({"items": "Add at least one product."})
    product_ids = [item["product"].pk for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise ValidationError({"items": "Each product should appear only once."})
    if discount_amount < 0:
        raise ValidationError({"discount_amount": "Sale discount cannot be negative."})


def _as_field_error(field, exc):
    """Re-keys a plain ValidationError under ``field`` (dict errors pass through)."""
    if hasattr(exc, "error_dict"):
        return exc
    return ValidationError({field: exc.messages})


@transaction.atomic
def replace_draft_cart(*, sale_id, items, customer=None, discount_amount=ZERO):
    """Replaces a draft's lines, customer and sale discount in one step.

    Side effects: locks the draft and its products (primary-key order); deletes
    the old lines and snapshots current prices for the new ones. Drafts never
    touch stock.
    """
    sale = _lock_draft_sale(sale_id)
    _check_cart(items, discount_amount)
    ensure_usable(customer)
    products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=[item["product"].pk for item in items])
        .order_by("pk")
    }
    sale.items.all().delete()
    sale.customer = customer
    sale.discount_amount = ZERO
    for item_data in items:
        product = products[item_data["product"].pk]
        item_discount = item_data.get("discount_amount", ZERO)
        _validate_line(
            product=product,
            quantity=item_data["quantity"],
            discount_amount=item_discount,
            unit_price=product.selling_price,
        )
        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=item_data["quantity"],
            unit_selling_price=product.selling_price,
            unit_cost_price=product.cost_price,
            discount_amount=item_discount,
        )
    sale.discount_amount = discount_amount
    try:
        _recalculate_totals(sale)
    except ValidationError as exc:
        raise _as_field_error("discount_amount", exc) from None
    return sale


@transaction.atomic
def checkout_sale(
    *,
    user,
    items,
    customer=None,
    discount_amount=ZERO,
    draft_id=None,
    sale_date=None,
    backdate_reason="",
    payment=None,
    client_transaction_id=None,
):
    """Creates (or completes a draft), finalizes and optionally pays a sale at once.

    Returns ``(sale, created)``. A repeated ``client_transaction_id`` returns the
    existing sale with ``created=False`` and changes nothing (idempotent retry).

    Side effects, all in one transaction: locks products in primary-key order,
    deducts stock (SALE movements), assigns the sale number, sets ``sale_date``,
    records the receipt when ``payment`` is given (needs ``sales.record_payment``)
    and writes a BACKDATED event for past dates (needs ``sales.backdate_sale``
    and a reason). Any failure leaves no trace.
    """
    if client_transaction_id:
        existing = Sale.objects.filter(
            client_transaction_id=client_transaction_id
        ).first()
        if existing:
            # Only a finalized sale by the same user counts as a retry; anything
            # else means the id was reused and must not hand back another sale.
            if (
                existing.created_by_id == user.pk
                and existing.status != Sale.Status.DRAFT
            ):
                return existing, False
            raise ValidationError(
                {
                    "client_transaction_id": (
                        "This checkout id was already used. Start a new sale."
                    )
                }
            )

    today = store_today()
    sale_date = sale_date or today
    if sale_date > today:
        raise ValidationError({"sale_date": "The date of sale can't be in the future."})
    backdated = sale_date < today
    if backdated:
        if not user.has_perm(BACKDATE_PERMISSION):
            raise PermissionDenied("You do not have permission to record past sales.")
        if not (backdate_reason or "").strip():
            raise ValidationError(
                {"backdate_reason": "Explain why this sale has a past date."}
            )
    if payment and not user.has_perm(RECORD_PAYMENT_PERMISSION):
        raise PermissionDenied("You do not have permission to record payments.")

    _check_cart(items, discount_amount)
    if draft_id:
        try:
            sale = replace_draft_cart(
                sale_id=draft_id,
                items=items,
                customer=customer,
                discount_amount=discount_amount,
            )
        except Sale.DoesNotExist:
            raise ValidationError(
                {"draft_id": "This draft no longer exists."}
            ) from None
    else:
        try:
            sale = create_draft_sale(
                user=user,
                items=items,
                customer=customer,
                discount_amount=discount_amount,
            )
        except ValidationError as exc:
            raise _as_field_error("items", exc) from None

    if client_transaction_id:
        sale.client_transaction_id = client_transaction_id
    sale.sale_date = sale_date
    sale.save(update_fields=["client_transaction_id", "sale_date", "updated_at"])

    try:
        finalize_sale(sale.pk, user)
    except ValidationError as exc:
        raise _as_field_error("items", exc) from None

    if payment:
        sale.refresh_from_db()
        if payment["amount"] > sale.total_amount:
            raise ValidationError(
                {
                    "payment": (
                        f"Amount paid can't exceed the total of {sale.total_amount}."
                    )
                }
            )
        try:
            record_payment(
                user=user,
                amount=payment["amount"],
                payment_method=payment["payment_method"],
                sale=sale,
                reference_number=payment.get("reference_number", ""),
            )
        except ValidationError as exc:
            raise _as_field_error("payment", exc) from None

    if backdated:
        SaleEvent.objects.create(
            sale=sale,
            action=SaleEvent.Action.BACKDATED,
            changes={"sale_date": [str(today), str(sale_date)]},
            reason=backdate_reason.strip(),
            performed_by=user,
        )
    return Sale.objects.get(pk=sale.pk), True


@transaction.atomic
def change_sale_customer(*, sale_id, user, customer, reason):
    """Links or changes the customer of a finalized (not cancelled) sale.

    Side effects: locks the sale; writes a CUSTOMER_CHANGED event with the old
    and new customer ids and the reason. Nothing else about the sale changes.
    """
    if not (reason or "").strip():
        raise ValidationError({"reason": "A reason is required."})
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if sale.status not in (Sale.Status.PENDING_PAYMENT, Sale.Status.COMPLETED):
        raise ValidationError(
            "Only completed or pending-payment sales can have their customer changed."
        )
    ensure_usable(customer)
    if customer is None:
        raise ValidationError({"customer_id": "Choose a customer."})
    if sale.customer_id == customer.pk:
        raise ValidationError({"customer_id": "This customer is already linked."})
    old_customer_id = sale.customer_id
    sale.customer = customer
    sale.save(update_fields=["customer", "updated_at"])
    SaleEvent.objects.create(
        sale=sale,
        action=SaleEvent.Action.CUSTOMER_CHANGED,
        changes={"customer": [old_customer_id, customer.pk]},
        reason=reason.strip(),
        performed_by=user,
    )
    return sale
