from django.db import models

# Create your models here.

# Customer ------------------------------
class Customer(models.Model):

    full_name = models.CharField(max_length=150)

    phone_number = models.CharField(
        max_length=30,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    address = models.TextField(
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    # Archive customers instead of permanently deleting them.
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(
                fields=["full_name"],
                name="customer_name_idx"
            ),
            models.Index(
                fields=["phone_number"],
                name="customer_phone_idx"
            ),
        ]

    def __str__(self):
        return self.full_name

