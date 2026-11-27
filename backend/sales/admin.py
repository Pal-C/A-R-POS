"""Register models in Django Admin"""

from django.contrib import admin

from .models import SaleEvent


@admin.register(SaleEvent)
class SaleEventAdmin(admin.ModelAdmin):
    """Read-only: sale history is append-only."""

    list_display = ["sale", "action", "performed_by", "created_at"]
    list_filter = ["action"]
    search_fields = ["sale__sale_number", "reason"]
    list_select_related = ["sale", "performed_by"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
