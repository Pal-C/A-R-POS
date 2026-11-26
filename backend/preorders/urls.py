from django.urls import path

from preorders.views import (
    PreOrderCancelView,
    PreOrderDetailView,
    PreOrderFulfillView,
    PreOrderHistoryView,
    PreOrderListCreateView,
    PreOrderPaymentsView,
    PreOrderStatusView,
    ProductArrivalView,
    ProductPreorderSummaryView,
)

urlpatterns = [
    path("", PreOrderListCreateView.as_view(), name="preorder-list-create"),
    path("<int:pk>/", PreOrderDetailView.as_view(), name="preorder-detail"),
    path("<int:pk>/status/", PreOrderStatusView.as_view(), name="preorder-status"),
    path("<int:pk>/fulfill/", PreOrderFulfillView.as_view(), name="preorder-fulfill"),
    path("<int:pk>/cancel/", PreOrderCancelView.as_view(), name="preorder-cancel"),
    path(
        "<int:pk>/payments/", PreOrderPaymentsView.as_view(), name="preorder-payments"
    ),
    path("<int:pk>/history/", PreOrderHistoryView.as_view(), name="preorder-history"),
    path(
        "products/<int:product_id>/summary/",
        ProductPreorderSummaryView.as_view(),
        name="preorder-product-summary",
    ),
    path(
        "products/<int:product_id>/arrivals/",
        ProductArrivalView.as_view(),
        name="preorder-product-arrivals",
    ),
]
