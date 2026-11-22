
from django.urls import path

from inventory.views import (
    InventoryMovementListView,
    InventoryMovementDetailView,
    RestockView,
    StockAdjustmentView,
    ReverseInventoryMovementView,
    LowStockProductsView,
    OutOfStockProductsView,
    InventorySummaryView,
)

urlpatterns = [
    # Movement history
    path(
        "movements/",
        InventoryMovementListView.as_view(),
        name="inventory-movement-list"
    ),
    path(
        "movements/<int:pk>/",
        InventoryMovementDetailView.as_view(),
        name="inventory-movement-detail"
    ),

    # Stock operations
    path(
        "restocks/",
        RestockView.as_view(),
        name="inventory-restock"
    ),
    path(
        "adjustments/",
        StockAdjustmentView.as_view(),
        name="inventory-adjustment"
    ),
    path(
        "movements/<int:pk>/reverse/",
        ReverseInventoryMovementView.as_view(),
        name="inventory-movement-reverse"
    ),

    # Inventory overview
    path(
        "low-stock/",
        LowStockProductsView.as_view(),
        name="inventory-low-stock"
    ),
    path(
        "out-of-stock/",
        OutOfStockProductsView.as_view(),
        name="inventory-out-of-stock"
    ),
    path(
        "summary/",
        InventorySummaryView.as_view(),
        name="inventory-summary"
    ),
]
