
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.models import Product
from inventory.models import InventoryMovement
from inventory.services import (
    deduct_stock_for_sale,
    reverse_movement,
)
from sales.models import Sale, SaleItem, Payment
from stringing.models import StringingOrder
from preorders.models import PreOrder


@transaction.atomic
def create_draft_sale(
    *,
    user,
    items,
    customer=None,
    discount_amount=Decimal("0.00"),
):
    """
    Creates a draft sale and its item snapshots.

    Does not deduct inventory. Inventory is deducted only
    when the sale is finalized.
    """

    if not items:
        raise ValidationError("A sale must contain at least one item.")

    if discount_amount < 0:
        raise ValidationError("Sale discount cannot be negative.")

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

    subtotal = Decimal("0.00")
    item_discounts = Decimal("0.00")

    for item_data in items:
        product_id = item_data["product"].pk
        product = products[product_id]
        quantity = item_data["quantity"]
        item_discount = item_data.get(
            "discount_amount",
            Decimal("0.00"),
        )

        if not product.is_active:
            raise ValidationError(
                f"{product.name} is inactive and cannot be sold."
            )

        if quantity <= 0:
            raise ValidationError(
                f"Quantity for {product.name} must be greater than zero."
            )

        if item_discount < 0:
            raise ValidationError("Item discount cannot be negative.")

        line_subtotal = product.selling_price * quantity

        if item_discount > line_subtotal:
            raise ValidationError(
                f"Discount for {product.name} exceeds its line subtotal."
            )

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_selling_price=product.selling_price,
            unit_cost_price=product.cost_price,
            discount_amount=item_discount,
        )

        subtotal += line_subtotal
        item_discounts += item_discount

    if discount_amount > subtotal - item_discounts:
        raise ValidationError(
            "Sale discount exceeds the remaining sale amount."
        )

    sale.discount_amount = discount_amount
    sale.subtotal = subtotal
    sale.total_amount = subtotal - item_discounts - discount_amount

    sale.save(
        update_fields=[
            "subtotal",
            "discount_amount",
            "total_amount",
            "updated_at",
        ]
    )

    return sale


@transaction.atomic
def finalize_sale(sale_id, user):
    sale = Sale.objects.select_for_update().get(pk=sale_id)

    if sale.status != Sale.Status.DRAFT:
        raise ValidationError("Only draft sales can be finalized.")

    items = list(
        sale.items.select_related("product").order_by("product_id")
    )

    if not items:
        raise ValidationError("Cannot finalize a sale without items.")

    subtotal = Decimal("0.00")
    item_discounts = Decimal("0.00")

    for item in items:
        subtotal += item.line_subtotal
        item_discounts += item.discount_amount

    if sale.discount_amount > subtotal - item_discounts:
        raise ValidationError(
            "The sale discount exceeds the remaining sale amount."
        )

    # Recalculate totals from the saved snapshots.
    sale.subtotal = subtotal
    sale.total_amount = (
        subtotal - item_discounts - sale.discount_amount
    )

    # Deduct inventory in a consistent product order.
    for item in items:
        deduct_stock_for_sale(
            product_id=item.product_id,
            quantity_sold=item.quantity,
            created_by=user,
            sale_item=item,
            reference_number=sale.sale_number or str(sale.pk),
        )

    sale.finalized_at = timezone.now()
    sale.status = Sale.Status.PENDING_PAYMENT

    sale.save(
        update_fields=[
            "subtotal",
            "total_amount",
            "finalized_at",
            "status",
            "updated_at",
        ]
    )

    return sale


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
    targets = [sale, stringing_order, preorder]

    if sum(target is not None for target in targets) != 1:
        raise ValidationError(
            "A payment must belong to exactly one order."
        )

    if amount <= 0:
        raise ValidationError("Payment amount must be positive.")

    if payment_type not in Payment.PaymentType.values:
        raise ValidationError("Invalid payment type.")

    if sale is not None:
        order = Sale.objects.select_for_update().get(pk=sale.pk)
        target_field = "sale"

        if order.status == Sale.Status.DRAFT:
            raise ValidationError(
                "Payments can only be recorded for finalized sales."
            )

        if (
            order.status == Sale.Status.CANCELLED
            and payment_type == Payment.PaymentType.RECEIPT
        ):
            raise ValidationError(
                "Cannot receive payment for a cancelled sale."
            )

    elif stringing_order is not None:
        order = StringingOrder.objects.select_for_update().get(
            pk=stringing_order.pk
        )
        target_field = "stringing_order"

        if (
            order.status == StringingOrder.Status.CANCELLED
            and payment_type == Payment.PaymentType.RECEIPT
        ):
            raise ValidationError(
                "Cannot receive payment for a cancelled stringing order."
            )

    else:
        order = PreOrder.objects.select_for_update().get(
            pk=preorder.pk
        )
        target_field = "preorder"

        if (
            order.status == PreOrder.Status.CANCELLED
            and payment_type == Payment.PaymentType.RECEIPT
        ):
            raise ValidationError(
                "Cannot receive payment for a cancelled pre-order."
            )

    payments = Payment.objects.filter(
        **{target_field: order},
        status=Payment.Status.POSTED,
    )

    received = sum(
        (
            payment.amount
            if payment.payment_type == Payment.PaymentType.RECEIPT
            else -payment.amount
        )
        for payment in payments
    )

    if payment_type == Payment.PaymentType.RECEIPT:
        if received + amount > order.total_amount:
            raise ValidationError(
                "Payment exceeds the outstanding balance."
            )

    elif payment_type == Payment.PaymentType.REFUND:
        if amount > received:
            raise ValidationError(
                "Refund cannot exceed the net amount received."
            )

    payment = Payment.objects.create(
        sale=order if target_field == "sale" else None,
        stringing_order=(
            order if target_field == "stringing_order" else None
        ),
        preorder=order if target_field == "preorder" else None,
        amount=amount,
        payment_method=payment_method,
        payment_type=payment_type,
        status=Payment.Status.POSTED,
        received_by=user,
        reference_number=reference_number,
        notes=notes,
    )

    # Sale status reflects the net amount received.
    if target_field == "sale" and order.status != Sale.Status.CANCELLED:
        updated_received = (
            received + amount
            if payment_type == Payment.PaymentType.RECEIPT
            else received - amount
        )

        order.status = (
            Sale.Status.COMPLETED
            if updated_received >= order.total_amount
            else Sale.Status.PENDING_PAYMENT
        )

        order.save(update_fields=["status", "updated_at"])

    return payment


@transaction.atomic
def cancel_sale(*, sale_id, user, reason):
    if not reason or not reason.strip():
        raise ValidationError("A cancellation reason is required.")

    sale = Sale.objects.select_for_update().get(pk=sale_id)

    if sale.status == Sale.Status.DRAFT:
        raise ValidationError(
            "Draft sales cannot be cancelled through this operation."
        )

    if sale.status == Sale.Status.CANCELLED:
        raise ValidationError("This sale has already been cancelled.")

    movements = InventoryMovement.objects.filter(
        sale_item__sale=sale,
        movement_type=InventoryMovement.MovementType.SALE,
    ).order_by("product_id", "pk")

    for movement in movements:
        reverse_movement(
            movement_id=movement.pk,
            created_by=user,
            reason=f"Cancellation of sale {sale.sale_number or sale.pk}: {reason}",
            reference_number=sale.sale_number or str(sale.pk),
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
