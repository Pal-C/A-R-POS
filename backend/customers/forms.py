from django import forms
from django.core.exceptions import ValidationError

from customers.services import ensure_usable


class ActiveCustomerOnChangeMixin:
    """
    ModelForm mixin for orders with a ``customer`` field (research R9).

    Refuses an archived customer when the customer is newly chosen (new
    order, or switched on an existing one), but still allows editing an
    existing order whose customer was archived later.
    """

    def clean_customer(self):
        customer = self.cleaned_data.get("customer")
        is_change = self.instance.pk is not None
        unchanged = is_change and self.instance.customer_id == getattr(
            customer, "pk", None
        )

        if not unchanged:
            try:
                ensure_usable(customer)
            except ValidationError as exc:
                raise forms.ValidationError(exc.messages) from None

        return customer
