"""
Backfill for existing stringing orders (research R8), run before the new
constraints are added:

- ``paid_in_full_at``: latest posted payment date for fully paid orders,
  ``created_at`` for zero-total orders.
- ``updated_at`` = ``created_at``.
- Legacy rows that would violate the new constraints get explicit
  placeholder values instead of failing the migration.
"""

from decimal import Decimal

from django.db import migrations
from django.db.models import F

LEGACY_REASON = "Cancelled before the audit trail existed (no reason recorded)."
NOT_RECORDED = "(not recorded)"


def backfill(apps, schema_editor):
    StringingOrder = apps.get_model("stringing", "StringingOrder")
    Payment = apps.get_model("sales", "Payment")

    StringingOrder.objects.update(updated_at=F("created_at"))

    for order in StringingOrder.objects.all().iterator():
        changed = []

        if not order.racket_description.strip():
            order.racket_description = NOT_RECORDED
            changed.append("racket_description")
        if not order.string_type.strip():
            order.string_type = NOT_RECORDED
            changed.append("string_type")

        if order.status == "COMPLETED" and order.completed_at is None:
            order.completed_at = order.created_at
            changed.append("completed_at")

        if order.status == "CANCELLED":
            if order.cancelled_at is None:
                order.cancelled_at = order.created_at
                changed.append("cancelled_at")
            if order.cancelled_by_id is None:
                order.cancelled_by = order.created_by
                changed.append("cancelled_by")
            if not order.cancellation_reason.strip():
                order.cancellation_reason = LEGACY_REASON
                changed.append("cancellation_reason")
        else:
            total = order.service_price - order.discount_amount
            payments = list(
                Payment.objects.filter(stringing_order=order, status="POSTED").order_by(
                    "payment_date", "pk"
                )
            )
            net = sum(
                (p.amount if p.payment_type == "RECEIPT" else -p.amount)
                for p in payments
            ) or Decimal("0.00")
            if net >= total:
                order.paid_in_full_at = (
                    payments[-1].payment_date if payments else order.created_at
                )
                changed.append("paid_in_full_at")

        if changed:
            # QuerySet.update keeps updated_at as backfilled above.
            values = {field: getattr(order, field) for field in changed}
            StringingOrder.objects.filter(pk=order.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [
        ("stringing", "0004_order_number_seq"),
        ("sales", "0004_customer_protect"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
