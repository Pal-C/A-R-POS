
from decimal import Decimal

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from sales.models import Sale
from inventory.models import InventoryMovement
from inventory.services import change_stock

from sales.models import Payment
from stringing.models import StringingOrder
from preorders.models import PreOrder


@transaction.atomic
def finalize_sale(sale_id, user):
    sale = Sale.objects.select_for_update().get(pk=sale_id)

    if sale.status != Sale.Status.DRAFT:
        raise ValidationError(
            "Only draft sales can be finalized."
        )

    items = list(
        sale.items.select_related("product").order_by("product_id")
    )

    if not items:
        raise ValidationError(
            "Cannot finalize a sale without items."
        )

    subtotal = Decimal("0.00")
    item_discounts = Decimal("0.00")

    for item in items:
        subtotal += item.line_subtotal
        item_discounts += item.discount_amount

    if sale.discount_amount > subtotal - item_discounts:
        raise ValidationError(
            "The sale discount exceeds the remaining sale amount."
        )

    sale.subtotal = subtotal
    sale.total_amount = (
        subtotal - item_discounts - sale.discount_amount
    )

    # Deduct inventory for each sale item.
    # Sorting helps keep product locks in a consistent order.
    for item in sorted(items, key=lambda x: x.product_id):
        change_stock(
            product_id=item.product_id,
            quantity_change=-item.quantity,
            movement_type=InventoryMovement.MovementType.SALE,
            user=user,
            reason=f"Sale {sale.sale_number or sale.pk}",
            sale_item=item,
            reference_number=sale.sale_number or str(sale.pk),
        )

    sale.finalized_at = timezone.now()

    # A sale is completed when finalized and some currency
    # has been received. Otherwise it remains pending payment.
    has_receipt = sale.payments.filter(
        status="POSTED",
        payment_type="RECEIPT"
    ).exists()

    sale.status = (
        Sale.Status.COMPLETED
        if has_receipt
        else Sale.Status.PENDING_PAYMENT
    )

    sale.save(update_fields=[
        "subtotal",
        "total_amount",
        "finalized_at",
        "status",
        "updated_at",
    ])

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

    if sale is not None:
        order = Sale.objects.select_for_update().get(pk=sale.pk)
        total_amount = order.total_amount
        payments = Payment.objects.filter(
            sale=order,
            status=Payment.Status.POSTED
        )
        if order.status == Sale.Status.CANCELLED:
            raise ValidationError("Cannot pay a cancelled sale.")

    elif stringing_order is not None:
        order = StringingOrder.objects.select_for_update().get(
            pk=stringing_order.pk
        )
        total_amount = order.total_amount
        payments = Payment.objects.filter(
            stringing_order=order,
            status=Payment.Status.POSTED
        )
        if order.status == StringingOrder.Status.CANCELLED:
            raise ValidationError(
                "Cannot pay a cancelled stringing order."
            )

    else:
        order = PreOrder.objects.select_for_update().get(
            pk=preorder.pk
        )
        total_amount = order.total_amount
        payments = Payment.objects.filter(
            preorder=order,
            status=Payment.Status.POSTED
        )
        if order.status == PreOrder.Status.CANCELLED:
            raise ValidationError("Cannot pay a cancelled pre-order.")

    received = sum(
        (
            payment.amount
            if payment.payment_type == Payment.PaymentType.RECEIPT
            else -payment.amount
        )
        for payment in payments
    )

    if payment_type == Payment.PaymentType.RECEIPT:
        if received + amount > total_amount:
            raise ValidationError(
                "Payment exceeds the outstanding balance."
            )

    elif payment_type == Payment.PaymentType.REFUND:
        if amount > received:
            raise ValidationError(
                "Refund cannot exceed the amount received."
            )

    payment = Payment.objects.create(
        sale=order if sale is not None else None,
        stringing_order=(
            order if stringing_order is not None else None
        ),
        preorder=order if preorder is not None else None,
        amount=amount,
        payment_method=payment_method,
        payment_type=payment_type,
        status=Payment.Status.POSTED,
        received_by=user,
        reference_number=reference_number,
        notes=notes,
    )

    if sale is not None and order.status == Sale.Status.PENDING_PAYMENT:
        order.status = Sale.Status.COMPLETED
        order.save(update_fields=["status", "updated_at"])

    return payment

