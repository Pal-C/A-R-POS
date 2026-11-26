from django.contrib import admin

from customers.models import Customer, CustomerAuditEvent


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """
    Archiving and deleting go through the API (customers.services) so they
    are permission-checked and audited; admin is for viewing and editing.
    """

    list_display = ["full_name", "phone_number", "email", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["full_name", "phone_number", "phone_normalized", "email"]
    readonly_fields = ["phone_normalized", "is_active", "created_at", "updated_at"]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerAuditEvent)
class CustomerAuditEventAdmin(admin.ModelAdmin):
    """Append-only audit trail: visible, never editable."""

    list_display = [
        "created_at",
        "action",
        "customer_name",
        "customer_ref",
        "performed_by",
    ]
    list_filter = ["action"]
    search_fields = ["customer_name", "customer_ref"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
