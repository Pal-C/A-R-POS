from django.db import models
from django.core.validators import MinValueValidator

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

    category = models.CharField(
        max_length=30,
        choices=Category.choices
    )
    subcategory = models.CharField(max_length=80, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    variant_description = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)

    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
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
                name="product_selling_price_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(cost_price__gte=0),
                name="product_cost_price_nonnegative"
            ),
        ]
        permissions = [
            ("adjust_stock", "Can adjust stock"),
            ("view_product_cost", "Can view product cost")
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
