"""
Shared payment read rules.

"Net paid" is the single definition of how much money an order has
received: posted receipts minus posted refunds; voided payments are
ignored. ``Sale.amount_paid`` applies the same rule in Python to
prefetched payments; these helpers apply it in the database so lists and
summaries don't load every payment (customers research R3).
"""

from decimal import Decimal

from django.db.models import (
    Case,
    DecimalField,
    F,
    OuterRef,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from sales.models import Payment

MONEY = DecimalField(max_digits=14, decimal_places=2)
ZERO = Value(Decimal("0.00"), output_field=MONEY)


def net_paid_expression(prefix=""):
    """
    Aggregate expression for net paid over the payments reachable through
    ``prefix`` (e.g. ``""`` on a Payment queryset, ``"payments__"`` on a
    Sale queryset). Evaluates to 0.00 when there are no payments.
    """
    posted = {f"{prefix}status": Payment.Status.POSTED}
    amount = F(f"{prefix}amount")

    return Coalesce(
        Sum(
            Case(
                When(
                    **posted,
                    **{f"{prefix}payment_type": Payment.PaymentType.RECEIPT},
                    then=amount,
                ),
                When(
                    **posted,
                    **{f"{prefix}payment_type": Payment.PaymentType.REFUND},
                    then=-amount,
                ),
                default=ZERO,
                output_field=MONEY,
            )
        ),
        ZERO,
        output_field=MONEY,
    )


def net_paid_subquery(order_field):
    """
    Per-row net paid for annotating an order queryset. ``order_field`` is
    the Payment foreign key pointing at that order: ``"sale"``,
    ``"stringing_order"`` or ``"preorder"``.
    """
    per_order = (
        Payment.objects.filter(**{order_field: OuterRef("pk")})
        .order_by()
        .values(order_field)
        .annotate(net=net_paid_expression())
        .values("net")
    )
    return Coalesce(Subquery(per_order, output_field=MONEY), ZERO, output_field=MONEY)
