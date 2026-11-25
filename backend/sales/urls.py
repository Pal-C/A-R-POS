
from django.urls import path

from sales.views import (
    SaleListCreateView,
    SaleDetailView,
    FinalizeSaleView,
    CancelSaleView,
    PaymentListCreateView,
)

urlpatterns = [
    path("", SaleListCreateView.as_view(), name="sale-list-create"),
    path("<int:pk>/", SaleDetailView.as_view(), name="sale-detail"),
    path(
        "<int:pk>/finalize/",
        FinalizeSaleView.as_view(),
        name="sale-finalize",
    ),
    path(
        "<int:pk>/cancel/",
        CancelSaleView.as_view(),
        name="sale-cancel",
    ),
    path(
        "payments/",
        PaymentListCreateView.as_view(),
        name="payment-list-create",
    ),
]
