from django.conf import settings
from django.db import models

# Pre-Order -----------------------------------------


class PreOrder(models.Model):
    """
    A customer's order for a product not yet in hand (spec 003). Business
    rules live in ``preorders.services``; amount paid, balance and payment
    state are derived from ``sales.Payment`` (see ``preorders.selectors``).
    Pre-orders never change product stock.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ORDERED = "ORDERED", "Ordered from Supplier"
        ARRIVED = "ARRIVED", "Arrived"
        FULFILLED = "FULFILLED", "Fulfilled"
        CANCELLED = "CANCELLED", "Cancelled"

    FINAL_STATUSES = (Status.FULFILLED, Status.CANCELLED)

    order_number = models.CharField(max_length=30, unique=True)

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="preorders"
    )

    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="preorders"
    )

    quantity = models.PositiveIntegerField()

    agreed_unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    expected_arrival_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ordered_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)

    fulfilled_at = models.DateTimeField(null=True, blank=True)
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fulfilled_preorders",
    )

    # Fulfilled and paid in full (research R2). Set by fulfillment, which
    # requires full payment; legacy fulfilled rows get it only once paid.
    settled_at = models.DateTimeField(null=True, blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_preorders",
    )
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="preorder_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(agreed_unit_price__gte=0),
                name="preorder_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="CANCELLED",
                        cancelled_at__isnull=False,
                        cancelled_by__isnull=False,
                    )
                    & ~models.Q(cancellation_reason="")
                )
                | (
                    ~models.Q(status="CANCELLED")
                    & models.Q(cancelled_at__isnull=True, cancelled_by__isnull=True)
                ),
                name="preorder_cancel_fields_consistent",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status="FULFILLED",
                    fulfilled_at__isnull=False,
                    fulfilled_by__isnull=False,
                )
                | (
                    ~models.Q(status="FULFILLED")
                    & models.Q(fulfilled_at__isnull=True, fulfilled_by__isnull=True)
                ),
                name="preorder_fulfilled_fields_consistent",
            ),
            models.CheckConstraint(
                condition=models.Q(settled_at__isnull=True)
                | models.Q(status="FULFILLED"),
                name="preorder_settled_only_when_fulfilled",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "-created_at"], name="preorder_status_created_idx"
            ),
            models.Index(
                fields=["product", "status"], name="preorder_product_status_idx"
            ),
            models.Index(
                fields=["expected_arrival_date"], name="preorder_expected_idx"
            ),
            models.Index(fields=["-created_at"], name="preorder_created_idx"),
        ]
        permissions = [
            ("cancel_preorder", "Can cancel pre-orders"),
            (
                "override_preorder_price",
                "Can change a pre-order's agreed price after payment",
            ),
        ]

    def __str__(self):
        return self.order_number

    @property
    def total_amount(self):
        """Agreed total: quantity times the agreed unit price."""
        return self.quantity * self.agreed_unit_price

    @property
    def is_settled(self):
        """
        Fulfilled and paid in full. Settled pre-orders take no more
        receipts, and a later refund does not reopen a balance. Legacy
        fulfilled pre-orders never paid in full are not settled and keep
        their real balance until collected.
        """
        return self.status == self.Status.FULFILLED and self.settled_at is not None


# Pre-Order audit trail -----------------------------------------


class PreOrderEvent(models.Model):
    """
    Append-only audit entry for a pre-order (FR-025). Payments are not
    copied here; the history view merges them in (research R6).
    """

    class EventType(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        CANCELLED = "CANCELLED", "Cancelled"

    preorder = models.ForeignKey(
        PreOrder, on_delete=models.PROTECT, related_name="events"
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    # UPDATED: {field: [old, new]}; money as strings, dates as ISO strings.
    changes = models.JSONField(default=dict, blank=True)
    # Arrival batch: {"arrival": {"received_quantity": n}}.
    extra = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="preorder_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["preorder", "created_at"], name="preorder_event_order_idx"
            ),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.preorder_id}"
