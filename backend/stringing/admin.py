from django import forms
from django.contrib import admin

from customers.forms import ActiveCustomerOnChangeMixin
from stringing.models import StringingOrder, StringingOrderEvent


class StringingOrderAdminForm(ActiveCustomerOnChangeMixin, forms.ModelForm):
    """Admin supplies the model and fields; this adds the customer guard."""


class StringingOrderEventInline(admin.TabularInline):
    model = StringingOrderEvent
    extra = 0
    can_delete = False
    readonly_fields = [
        "event_type",
        "from_status",
        "to_status",
        "changes",
        "reason",
        "performed_by",
        "created_at",
    ]
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StringingOrder)
class StringingOrderAdmin(admin.ModelAdmin):
    """
    Read-only: orders change only through the stringing services so every
    change is validated and audited (FR-024, FR-025).
    """

    form = StringingOrderAdminForm
    list_display = [
        "order_number",
        "customer",
        "status",
        "service_price",
        "has_stencil",
        "has_grip",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["order_number", "customer__full_name", "racket_description"]
    autocomplete_fields = ["customer"]
    inlines = [StringingOrderEventInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StringingOrderEvent)
class StringingOrderEventAdmin(admin.ModelAdmin):
    list_display = ["order", "event_type", "from_status", "to_status", "created_at"]
    list_filter = ["event_type"]
    search_fields = ["order__order_number"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
