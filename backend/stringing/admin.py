from django import forms
from django.contrib import admin

from customers.forms import ActiveCustomerOnChangeMixin
from stringing.models import StringingOrder


class StringingOrderAdminForm(ActiveCustomerOnChangeMixin, forms.ModelForm):
    """Admin supplies the model and fields; this adds the customer guard."""


@admin.register(StringingOrder)
class StringingOrderAdmin(admin.ModelAdmin):
    form = StringingOrderAdminForm
    list_display = ["order_number", "customer", "status", "service_price", "created_at"]
    list_filter = ["status"]
    search_fields = ["order_number", "customer__full_name", "racket_description"]
    autocomplete_fields = ["customer"]
