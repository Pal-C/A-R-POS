"""Test data helpers for the stringing app."""

from decimal import Decimal

from django.contrib.auth.models import Permission

from customers.models import Customer
from sales.models import Payment
from sales.tests.factories import make_user as _make_user
from stringing.services import create_stringing_order

_counter = {"n": 0}

ALL_PERMISSIONS = (
    "sales.record_payment",
    "sales.process_refund",
    "stringing.cancel_stringingorder",
    "stringing.view_stringing_financials",
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
    values = {"full_name": f"Stringing Customer {_next()}", "is_active": True}
    values.update(overrides)
    return Customer.objects.create(**values)


def make_order(user=None, **overrides):
    """Creates an order through the service (so it gets a real number)."""
    values = {
        "user": user or make_user(),
        "customer": None,
        "racket_description": "Yonex Astrox 88D",
        "string_type": "BG80",
        "tension": "26 lbs",
        "service_price": Decimal("450.00"),
        "discount_amount": Decimal("50.00"),
        "direct_cost": Decimal("180.00"),
    }
    values.update(overrides)
    return create_stringing_order(**values)


def make_payment(order, amount, *, user=None, payment_type=Payment.PaymentType.RECEIPT):
    """Records a payment through the sales service (keeps payment state in sync)."""
    from sales.services import process_refund, record_payment

    user = user or order.created_by
    if payment_type == Payment.PaymentType.REFUND:
        payment = process_refund(
            user=user,
            amount=Decimal(amount),
            payment_method=Payment.Method.CASH,
            reason="Test refund",
            stringing_order=order,
        )
    else:
        payment = record_payment(
            user=user,
            amount=Decimal(amount),
            payment_method=Payment.Method.CASH,
            stringing_order=order,
        )
    order.refresh_from_db()
    return payment
