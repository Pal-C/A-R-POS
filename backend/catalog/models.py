from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Length, Trim
from django.db.models.lookups import GreaterThan

# Create your models here.

# Product


class Product(models.Model):
    class Category(models.TextChoices):
        RACKET = "RACKET", "Racket"
        SPORTS_EQUIPMENT = "SPORTS_EQUIPMENT", "Sports Equipment"
        ACCESSORIES = "ACCESSORIES", "Accessories"
        APPAREL = "APPAREL", "Apparel"
        OTHER = "OTHER", "Other"

    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)

    category = models.CharField(max_length=30, choices=Category.choices)
    subcategory = models.CharField(max_length=80, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    variant_description = models.CharField(max_length=150, blank=True)
    model = models.CharField(max_length=100, blank=True)
    supplier = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)

    selling_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )

    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(selling_price__gte=0),
                name="product_selling_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(cost_price__gte=0),
                name="product_cost_price_nonnegative",
            ),
        ]
        permissions = [
            ("adjust_stock", "Can adjust stock"),
            ("view_product_cost", "Can view product cost"),
        ]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["stock_quantity"]),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self):
        return self.stock_quantity == 0

    @property
    def stock_status(self):
        if self.stock_quantity == 0:
            return "OUT_OF_STOCK"

        if self.is_low_stock:
            return "LOW_STOCK"

        return "IN_STOCK"


class ProductEvent(models.Model):
    """Append-only audit history of product changes (research R6).

    Stock changes themselves live in ``inventory.InventoryMovement``; an UPDATED
    event that changed stock references the movement in ``changes["movement_id"]``.
    """

    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        DEACTIVATED = "DEACTIVATED", "Deactivated"
        REACTIVATED = "REACTIVATED", "Reactivated"

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="events"
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    changes = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="product_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action="CREATED")
                | models.Q(GreaterThan(Length(Trim("reason")), 0)),
                name="productevent_reason_required",
            ),
        ]
        indexes = [models.Index(fields=["product", "-created_at"])]

    def __str__(self):
        return f"{self.product_id} {self.action} at {self.created_at:%Y-%m-%d %H:%M}"
