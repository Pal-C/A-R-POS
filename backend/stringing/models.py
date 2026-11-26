from django.conf import settings
from django.db import models

# Create your models here.

# Stringing Order ---------------------------------

class StringingOrder(models.Model):

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        READY = "READY", "Ready for Pickup"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    order_number = models.CharField(max_length=30, unique=True)

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stringing_orders"
    )

    racket_description = models.CharField(max_length=150)
    string_type = models.CharField(max_length=150)
    tension = models.CharField(max_length=50, blank=True)

    service_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    direct_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(service_price__gte=0),
                name="stringing_price_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="stringing_discount_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(direct_cost__gte=0),
                name="stringing_cost_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    discount_amount__lte=models.F("service_price")
                ),
                name="stringing_discount_not_above_price"
            ),
        ]
    permissions = [
        ("manage_stringing_orders", "Can manage stringing orders")
    ]

    def __str__(self):
        return self.order_number

    @property
    def total_amount(self):
        return self.service_price - self.discount_amount
