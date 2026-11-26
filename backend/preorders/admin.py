from django import forms
from django.contrib import admin

from customers.forms import ActiveCustomerOnChangeMixin
from preorders.models import PreOrder


class PreOrderAdminForm(ActiveCustomerOnChangeMixin, forms.ModelForm):
    """Admin supplies the model and fields; this adds the customer guard."""


@admin.register(PreOrder)
class PreOrderAdmin(admin.ModelAdmin):
    form = PreOrderAdminForm
    list_display = ["order_number", "customer", "product", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["order_number", "customer__full_name"]
    autocomplete_fields = ["customer"]
