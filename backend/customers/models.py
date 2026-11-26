from django.conf import settings
from django.db import models

from customers.phone import normalize_phone


# Customer ------------------------------
class Customer(models.Model):

    full_name = models.CharField(max_length=150)

    phone_number = models.CharField(
        max_length=30,
        blank=True
    )

    # Digits-only form of phone_number used for search (research R1).
    # Derived in save() so every write path, including Django admin, keeps it
    # in sync (plan.md, Complexity Tracking).
    phone_normalized = models.CharField(
        max_length=30,
        blank=True,
        editable=False,
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
    # Changed only through customers.services archive/reactivate.
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name", "id"]
        indexes = [
            models.Index(
                fields=["full_name"],
                name="customer_name_idx"
            ),
            models.Index(
                fields=["phone_number"],
                name="customer_phone_idx"
            ),
            models.Index(
                fields=["phone_normalized"],
                name="customer_phone_norm_idx"
            ),
            models.Index(
                fields=["is_active", "full_name"],
                name="customer_active_name_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(full_name__regex=r"\S"),
                name="customer_full_name_not_blank",
            ),
        ]
        permissions = [
            ("archive_customer", "Can archive and reactivate customers"),
        ]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        self.phone_normalized = normalize_phone(self.phone_number)

        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "phone_number" in update_fields:
            kwargs["update_fields"] = {*update_fields, "phone_normalized"}

        super().save(*args, **kwargs)


# Customer audit trail ------------------------------
class CustomerAuditEvent(models.Model):
    """
    Append-only record of archive, reactivate and delete actions (FR-021).

    ``customer_ref`` is a plain integer rather than a foreign key so the
    record survives the customer's deletion (research R5).
    """

    class Action(models.TextChoices):
        ARCHIVED = "ARCHIVED", "Archived"
        REACTIVATED = "REACTIVATED", "Reactivated"
        DELETED = "DELETED", "Deleted"

    action = models.CharField(max_length=20, choices=Action.choices)
    customer_ref = models.PositiveIntegerField(db_index=True)
    customer_name = models.CharField(max_length=150)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_audit_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["customer_ref", "-created_at"],
                name="customer_audit_ref_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action}: {self.customer_name} (#{self.customer_ref})"
