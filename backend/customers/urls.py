from django.urls import path

from customers.views import (
    ArchiveCustomerView,
    CustomerDetailView,
    CustomerListCreateView,
    CustomerPreordersView,
    CustomerSalesView,
    CustomerStringingOrdersView,
    PhoneMatchesView,
    ReactivateCustomerView,
)

urlpatterns = [
    path("", CustomerListCreateView.as_view(), name="customer-list-create"),
    path("phone-matches/", PhoneMatchesView.as_view(), name="customer-phone-matches"),
    path("<int:pk>/", CustomerDetailView.as_view(), name="customer-detail"),
    path(
        "<int:pk>/archive/", ArchiveCustomerView.as_view(), name="customer-archive"
    ),
    path(
        "<int:pk>/reactivate/",
        ReactivateCustomerView.as_view(),
        name="customer-reactivate",
    ),
    path("<int:pk>/sales/", CustomerSalesView.as_view(), name="customer-sales"),
    path(
        "<int:pk>/stringing-orders/",
        CustomerStringingOrdersView.as_view(),
        name="customer-stringing-orders",
    ),
    path(
        "<int:pk>/preorders/",
        CustomerPreordersView.as_view(),
        name="customer-preorders",
    ),
]
