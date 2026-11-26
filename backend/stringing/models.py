from django.conf import settings
from django.db import models
from django.db.models.functions import Length, Trim

# Stringing Order ---------------------------------


class StringingOrder(models.Model):
    """
    A racket stringing job (spec 002). Business rules live in
    ``stringing.services``; amount paid, balance and payment state are
    derived from ``sales.Payment`` (see ``stringing.selectors``).
    """

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        READY = "READY", "Ready for Pickup"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    FINAL_STATUSES = (Status.COMPLETED, Status.CANCELLED)

    order_number = models.CharField(max_length=30, unique=True)

    # PROTECT: a customer with stringing orders can never be deleted
    # (customers FR-019).
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stringing_orders",
    )

    racket_description = models.CharField(max_length=150)
    string_type = models.CharField(max_length=150)
    tension = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    service_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    direct_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Revenue recognition date: when the balance last reached 0.00 (R2/R3).
    paid_in_full_at = models.DateTimeField(null=True, blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_stringing_orders",
    )
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(service_price__gte=0),
                name="stringing_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="stringing_discount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(direct_cost__gte=0),
                name="stringing_cost_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__lte=models.F("service_price")),
                name="stringing_discount_not_above_price",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    models.lookups.GreaterThan(Length(Trim("racket_description")), 0)
                ),
                name="stringing_racket_not_blank",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    models.lookups.GreaterThan(Length(Trim("string_type")), 0)
                ),
                name="stringing_string_type_not_blank",
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
                name="stringing_cancel_fields_consistent",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="COMPLETED")
                | models.Q(completed_at__isnull=False),
                name="stringing_completed_has_time",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "-created_at"],
                name="stringing_status_created_idx",
            ),
            models.Index(fields=["-created_at"], name="stringing_created_idx"),
            models.Index(fields=["paid_in_full_at"], name="stringing_paid_full_idx"),
        ]
        permissions = [
            ("cancel_stringingorder", "Can cancel stringing orders"),
            (
                "view_stringing_financials",
                "Can view stringing direct cost, profit and revenue reports",
            ),
        ]

    def __str__(self):
        return self.order_number

    @property
    def total_amount(self):
        """Amount the customer owes for the service: price minus discount."""
        return self.service_price - self.discount_amount

    @property
    def is_settled(self):
        """
        Completed and paid in full. Settled orders show no balance, take no
        more receipts, and keep counting toward revenue after a refund made
        after pickup (FR-028). Legacy completed orders that were never paid
        in full are not settled and keep their real balance.
        """
        return self.status == self.Status.COMPLETED and self.paid_in_full_at is not None

    @property
    def profit(self):
        """Total due minus the direct cost of the job."""
        return self.total_amount - self.direct_cost


# Stringing Order audit trail ---------------------------------


class StringingOrderEvent(models.Model):
    """
    Append-only audit entry for a stringing order (FR-025). Payments are
    not copied here; the history view merges them in (research R4).
    """

    class EventType(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        CANCELLED = "CANCELLED", "Cancelled"

    order = models.ForeignKey(
        StringingOrder,
        on_delete=models.PROTECT,
        related_name="events",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    # UPDATED: {field: [old, new]}, money as strings.
    changes = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stringing_order_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["order", "created_at"],
                name="stringing_event_order_idx",
            ),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.order_id}"
