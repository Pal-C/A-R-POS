from django.urls import path

from sales.views import (
    CancelSaleView,
    CheckoutView,
    DraftCartView,
    FinalizeSaleView,
    PaymentListCreateView,
    SaleCustomerView,
    SaleDetailView,
    SaleItemAddView,
    SaleItemDetailView,
    SaleListCreateView,
)

urlpatterns = [
    path("", SaleListCreateView.as_view(), name="sale-list-create"),
    path("checkout/", CheckoutView.as_view(), name="sale-checkout"),
    path("<int:pk>/draft/", DraftCartView.as_view(), name="sale-draft-cart"),
    path("<int:pk>/customer/", SaleCustomerView.as_view(), name="sale-customer"),
    path("<int:pk>/", SaleDetailView.as_view(), name="sale-detail"),
    path(
        "<int:pk>/items/",
        SaleItemAddView.as_view(),
        name="sale-item-add",
    ),
    path(
        "<int:pk>/items/<int:item_pk>/",
        SaleItemDetailView.as_view(),
        name="sale-item-detail",
    ),
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
