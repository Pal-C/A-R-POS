"""Test data helpers for the preorders app."""

from decimal import Decimal

from django.contrib.auth.models import Permission

from catalog.models import Product
from customers.models import Customer
from preorders.services import create_preorder
from sales.models import Payment
from sales.tests.factories import make_user as _make_user

_counter = {"n": 0}

ALL_PERMISSIONS = (
    "sales.record_payment",
    "sales.process_refund",
    "preorders.cancel_preorder",
    "preorders.override_preorder_price",
)


def _next():
    _counter["n"] += 1
    return _counter["n"]


def make_user(*, perms=(), **kwargs):
    """A user with the given ``app_label.codename`` permissions."""
    user = _make_user(**kwargs)
    for perm in perms:
        app_label, codename = perm.split(".")
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
    return user


def make_customer(**overrides):
    values = {"full_name": f"Pre-order Customer {_next()}", "is_active": True}
    values.update(overrides)
    return Customer.objects.create(**values)


def make_product(**overrides):
    n = _next()
    values = {
        "sku": f"PO-SKU-{n:04d}",
        "name": f"Pre-order Racket {n}",
        "category": Product.Category.RACKET,
        "selling_price": Decimal("5000.00"),
        "cost_price": Decimal("3500.00"),
        "stock_quantity": 0,
        "is_active": True,
    }
    values.update(overrides)
    return Product.objects.create(**values)


def make_preorder(user=None, **overrides):
    """Creates a pre-order through the service (so it gets a real number)."""
    values = {
        "user": user or make_user(),
        "quantity": 2,
        "agreed_unit_price": Decimal("5000.00"),
    }
    values.update(overrides)
    values.setdefault("customer", make_customer())
    values.setdefault("product", make_product())
    return create_preorder(**values)


def make_payment(
    preorder, amount, *, user=None, payment_type=Payment.PaymentType.RECEIPT
):
    """Records a payment through the sales service."""
    from sales.services import process_refund, record_payment

    user = user or preorder.created_by
    if payment_type == Payment.PaymentType.REFUND:
        payment = process_refund(
            user=user,
            amount=Decimal(amount),
            payment_method=Payment.Method.CASH,
            reason="Test refund",
            preorder=preorder,
        )
    else:
        payment = record_payment(
            user=user,
            amount=Decimal(amount),
            payment_method=Payment.Method.CASH,
            preorder=preorder,
        )
    preorder.refresh_from_db()
    return payment
