from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.


class User(AbstractUser):
    """
    Custom user model for Ace&Rally staff accounts.

    Authentication fields and password handling are inherited
    from Django's AbstractUser.
    """
    pass

# Staff Profile ---------------------------------------------------
class StaffProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="staff_profile"
    )

    employee_code = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )

    phone_number = models.CharField(
        max_length=30,
        blank=True
    )

    job_title = models.CharField(
        max_length=80,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]
        permissions = [
            ("manage_staff_accounts", "Can create and manage staff accounts"),
            ("assign_staff_roles", "Can assign roles to staff accounts"),
        ]

    def __str__(self):
        return self.user.get_full_name() or self.user.username
