"""Small helpers for building sales test data."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from catalog.models import Product
from customers.models import Customer

User = get_user_model()

_counter = {"n": 0}


def _next():
    _counter["n"] += 1
    return _counter["n"]


def make_user(*, permissions=(), **kwargs):
    n = _next()
    user = User.objects.create_user(
        username=kwargs.pop("username", f"user{n}"),
        password="test-password",
        **kwargs,
    )
    if permissions:
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="sales",
                codename__in=permissions,
            )
        )
    return user


def make_product(**overrides):
    n = _next()
    values = {
        "sku": f"SKU-{n:04d}",
        "name": f"Product {n}",
        "category": Product.Category.RACKET,
        "selling_price": Decimal("1500.00"),
        "cost_price": Decimal("1000.00"),
        "stock_quantity": 10,
        "is_active": True,
    }
    values.update(overrides)
    return Product.objects.create(**values)


def make_customer(**overrides):
    values = {"full_name": f"Customer {_next()}", "is_active": True}
    values.update(overrides)
    return Customer.objects.create(**values)


def line(product, quantity, discount="0.00"):
    return {
        "product": product,
        "quantity": quantity,
        "discount_amount": Decimal(discount),
    }
