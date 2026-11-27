"""Register models in Django Admin"""

from django.contrib import admin

from .models import ProductEvent


@admin.register(ProductEvent)
class ProductEventAdmin(admin.ModelAdmin):
    """Read-only: product history is append-only."""

    list_display = ["product", "action", "performed_by", "created_at"]
    list_filter = ["action"]
    search_fields = ["product__name", "product__sku", "reason"]
    list_select_related = ["product", "performed_by"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
