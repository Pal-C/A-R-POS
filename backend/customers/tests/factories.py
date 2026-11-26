"""Test data helpers for the customers app."""

from decimal import Decimal

from django.contrib.auth.models import Permission

from customers.models import Customer
from preorders.models import PreOrder
from sales.models import Payment
from sales.services import create_draft_sale, finalize_sale, record_payment
from sales.tests.factories import line, make_product
from sales.tests.factories import make_user as _make_user
from stringing.models import StringingOrder

_counter = {"n": 0}


def _next():
    _counter["n"] += 1
    return _counter["n"]


def make_user(*, permissions=(), **kwargs):
    """Creates a user with the given ``customers`` app permission codenames."""
    user = _make_user(**kwargs)
    if permissions:
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="customers",
                codename__in=permissions,
            )
        )
    return user


def make_customer(**overrides):
    values = {"full_name": f"Customer {_next()}", "is_active": True}
    values.update(overrides)
    return Customer.objects.create(**values)


def make_finalized_sale(customer, user, *, items=None, paid=None):
    """A finalized sale for ``customer``; optionally records a cash receipt."""
    sale = create_draft_sale(
        user=user,
        customer=customer,
        items=items or [line(make_product(), 1)],
    )
    sale = finalize_sale(sale.pk, user)
    if paid:
        record_payment(
            user=user,
            sale=sale,
            amount=Decimal(paid),
            payment_method=Payment.Method.CASH,
        )
    sale.refresh_from_db()
    return sale


def make_stringing_order(customer, user, **overrides):
    """Delegates to the stringing factory so orders get real order numbers."""
    from stringing.tests.factories import make_order

    overrides.pop("order_number", None)
    status = overrides.pop("status", None)
    values = {
        "customer": customer,
        "racket_description": "Test racket",
        "string_type": "BG66",
        "tension": "26 lbs",
        "service_price": Decimal("450.00"),
        "discount_amount": Decimal("0.00"),
        "direct_cost": Decimal("0.00"),
    }
    values.update(overrides)
    order = make_order(user, **values)
    if status is not None:
        # History tests only need the status value; bypass the workflow.
        extra = {}
        if status == StringingOrder.Status.COMPLETED:
            extra["completed_at"] = order.created_at
        if status == StringingOrder.Status.CANCELLED:
            extra.update(
                cancelled_at=order.created_at,
                cancelled_by=user,
                cancellation_reason="Test cancellation",
                paid_in_full_at=None,
            )
        StringingOrder.objects.filter(pk=order.pk).update(status=status, **extra)
        order.refresh_from_db()
    return order


def make_preorder(customer, user, **overrides):
    values = {
        "order_number": f"PO-{_next():05d}",
        "customer": customer,
        "product": overrides.pop("product", None) or make_product(),
        "quantity": 1,
        "agreed_unit_price": Decimal("5000.00"),
        "created_by": user,
    }
    values.update(overrides)
    return PreOrder.objects.create(**values)
