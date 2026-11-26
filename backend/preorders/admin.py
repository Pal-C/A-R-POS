from django import forms
from django.contrib import admin

from customers.forms import ActiveCustomerOnChangeMixin
from preorders.models import PreOrder, PreOrderEvent


class PreOrderAdminForm(ActiveCustomerOnChangeMixin, forms.ModelForm):
    """Admin supplies the model and fields; this adds the customer guard."""


class PreOrderEventInline(admin.TabularInline):
    model = PreOrderEvent
    extra = 0
    can_delete = False
    readonly_fields = [
        "event_type",
        "from_status",
        "to_status",
        "changes",
        "extra",
        "reason",
        "performed_by",
        "created_at",
    ]
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PreOrder)
class PreOrderAdmin(admin.ModelAdmin):
    """
    Read-only: pre-orders change only through the pre-order services so
    every change is validated and audited (FR-024, FR-025).
    """

    form = PreOrderAdminForm
    list_display = ["order_number", "customer", "product", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["order_number", "customer__full_name", "product__name"]
    autocomplete_fields = ["customer"]
    inlines = [PreOrderEventInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PreOrderEvent)
class PreOrderEventAdmin(admin.ModelAdmin):
    list_display = ["preorder", "event_type", "from_status", "to_status", "created_at"]
    list_filter = ["event_type"]
    search_fields = ["preorder__order_number"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
