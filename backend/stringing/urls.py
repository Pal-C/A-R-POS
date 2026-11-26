from django.urls import path

from stringing.views import (
    StringingOrderCancelView,
    StringingOrderDetailView,
    StringingOrderHistoryView,
    StringingOrderListCreateView,
    StringingOrderPaymentsView,
    StringingOrderStatusView,
    StringingRevenueReportView,
)

urlpatterns = [
    path(
        "orders/",
        StringingOrderListCreateView.as_view(),
        name="stringing-order-list-create",
    ),
    path(
        "orders/<int:pk>/",
        StringingOrderDetailView.as_view(),
        name="stringing-order-detail",
    ),
    path(
        "orders/<int:pk>/status/",
        StringingOrderStatusView.as_view(),
        name="stringing-order-status",
    ),
    path(
        "orders/<int:pk>/cancel/",
        StringingOrderCancelView.as_view(),
        name="stringing-order-cancel",
    ),
    path(
        "orders/<int:pk>/payments/",
        StringingOrderPaymentsView.as_view(),
        name="stringing-order-payments",
    ),
    path(
        "orders/<int:pk>/history/",
        StringingOrderHistoryView.as_view(),
        name="stringing-order-history",
    ),
    path(
        "reports/revenue/",
        StringingRevenueReportView.as_view(),
        name="stringing-revenue-report",
    ),
]
