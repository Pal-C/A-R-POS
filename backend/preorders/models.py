from django.conf import settings
from django.db import models

# Create your models here.

# Pre-Order -----------------------------------------
class PreOrder(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ORDERED = "ORDERED", "Ordered from Supplier"
        ARRIVED = "ARRIVED", "Arrived"
        FULFILLED = "FULFILLED", "Fulfilled"
        CANCELLED = "CANCELLED", "Cancelled"

    order_number = models.CharField(max_length=30, unique=True)

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="preorders"
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="preorders"
    )

    quantity = models.PositiveIntegerField()

    agreed_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    expected_arrival_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="preorder_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(agreed_unit_price__gte=0),
                name="preorder_price_nonnegative"
            ),
        ]

    @property
    def total_amount(self):
        return self.quantity * self.agreed_unit_price
