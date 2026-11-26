import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

# Create your models here.

#Sale --------------------------------------------------
class Sale(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pending Payment"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    sale_number = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )

    # Used to identify repeated offline submissions.
    client_transaction_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales"
    )


    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_sales"
    )

    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )


    created_at = models.DateTimeField(auto_now_add=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_sales"
    )
    cancellation_reason = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["customer", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="sale_subtotal_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="sale_discount_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="sale_total_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__lte=models.F("subtotal")),
                name="sale_discount_not_above_subtotal"
            )
        ]
        permissions = [
            ("finalize_sale", "Can finalize sales"),
            ("cancel_sale", "Can cancel finalized sales"),
            ("apply_sale_discount", "Can apply sale discounts"),
            ("view_sales_reports", "Can view sales reports"),
        ]

    def __str__(self):
        return self.sale_number or f"Sale #{self.pk}"

    @property
    def item_discount_total(self):
        """Sum of line-level discounts, derived from the stored totals."""
        return self.subtotal - self.discount_amount - self.total_amount

    @property
    def amount_paid(self):
        """
        Net amount received: posted receipts minus posted refunds.

        This is the canonical "net paid" rule; ``sales.selectors`` applies the
        same rule in the database for lists and summaries.

        Iterates ``payments.all()`` so a ``prefetch_related("payments")``
        on the queryset is reused instead of issuing a query per sale.
        """
        return sum(
            (
                payment.amount
                if payment.payment_type == Payment.PaymentType.RECEIPT
                else -payment.amount
            )
            for payment in self.payments.all()
            if payment.status == Payment.Status.POSTED
        ) or Decimal("0.00")

    @property
    def balance(self):
        """Amount the customer still owes. Zero for drafts and cancelled sales."""
        if self.status in (self.Status.DRAFT, self.Status.CANCELLED):
            return Decimal("0.00")
        return max(self.total_amount - self.amount_paid, Decimal("0.00"))

    @property
    def refund_due(self):
        """Money still to be returned to the customer for a cancelled sale."""
        if self.status != self.Status.CANCELLED:
            return Decimal("0.00")
        return max(self.amount_paid, Decimal("0.00"))

# SaleItem --------------------------------------------------
class SaleItem(models.Model):

    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="items"
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="sale_items"
    )

    quantity = models.PositiveIntegerField()

    # Historical price snapshots:
    unit_selling_price = models.DecimalField(
        max_digits=10, decimal_places=2
    )
    unit_cost_price = models.DecimalField(
        max_digits=10, decimal_places=2
    )

    # Discount applied to this individual line.
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sale_item_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_selling_price__gte=0),
                name="sale_selling_price_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost_price__gte=0),
                name="sale_cost_price_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="sale_item_discount_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    discount_amount__lte=(
                        models.F("quantity") *
                        models.F("unit_selling_price")
                    )
                ),
                name="saleitem_discount_not_above_subtotal"
            ),
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def line_subtotal(self):
        return self.quantity * self.unit_selling_price

    @property
    def line_total(self):
        return self.line_subtotal - self.discount_amount

    @property
    def gross_profit(self):
        return (
            self.line_total
            - (self.quantity * self.unit_cost_price)
        )

# Payment --------------------------------------------------
class Payment(models.Model):

    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        GCASH = "GCASH", "GCash"
        MAYA = "MAYA", "Maya"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
        CARD = "CARD", "Card"
        OTHER = "OTHER", "Other"

    class PaymentType(models.TextChoices):
        RECEIPT = "RECEIPT", "Money Received"
        REFUND = "REFUND", "Money Refunded"

    class Status(models.TextChoices):
        POSTED = "POSTED", "Posted"
        VOIDED = "VOIDED", "Voided"

    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments"
    )

    stringing_order = models.ForeignKey(
        "stringing.StringingOrder",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments"
    )

    preorder = models.ForeignKey(
        "preorders.PreOrder",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    payment_method = models.CharField(
        max_length=20,
        choices=Method.choices
    )

    payment_type = models.CharField(
        max_length=10,
        choices=PaymentType.choices,
        default=PaymentType.RECEIPT
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.POSTED
    )

    payment_date = models.DateTimeField(default=timezone.now)

    reference_number = models.CharField(
        max_length=100, blank=True
    )
    notes = models.TextField(blank=True)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_payments"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_positive"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        sale__isnull=False,
                        stringing_order__isnull=True,
                        preorder__isnull=True
                    )
                    | models.Q(
                        sale__isnull=True,
                        stringing_order__isnull=False,
                        preorder__isnull=True
                    )
                    | models.Q(
                        sale__isnull=True,
                        stringing_order__isnull=True,
                        preorder__isnull=False
                    )
                ),
                name="payment_exactly_one_order"
            ),
        ]
        permissions = [
            ("record_payment", "Can record payments"),
            ("process_refund", "Can process refunds"),
        ]

    def __str__(self):
        return f"{self.payment_type}: ₱{self.amount}"
