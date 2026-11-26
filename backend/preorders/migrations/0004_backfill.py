"""
Backfill for existing pre-orders (research R9), run before the new
constraints are added. History before this feature is unknown, so legacy
rows get explicit placeholder values instead of failing the migration.
"""

from decimal import Decimal

from django.db import migrations
from django.db.models import F

LEGACY_REASON = "Cancelled before the audit trail existed (no reason recorded)."


def backfill(apps, schema_editor):
    PreOrder = apps.get_model("preorders", "PreOrder")

    PreOrder.objects.update(updated_at=F("created_at"))

    PreOrder.objects.filter(status="FULFILLED", fulfilled_at__isnull=True).update(
        fulfilled_at=F("created_at")
    )
    PreOrder.objects.filter(status="FULFILLED", fulfilled_by__isnull=True).update(
        fulfilled_by=F("created_by")
    )
    # The old model let fulfilled_at be set on any status; the new
    # constraint allows it only on FULFILLED rows.
    PreOrder.objects.exclude(status="FULFILLED").filter(
        fulfilled_at__isnull=False
    ).update(fulfilled_at=None)

    # Only fulfilled rows that were actually paid in full are settled;
    # unpaid ones keep their real balance so it can still be collected.
    Payment = apps.get_model("sales", "Payment")
    for preorder in PreOrder.objects.filter(status="FULFILLED").iterator():
        net = sum(
            (p.amount if p.payment_type == "RECEIPT" else -p.amount)
            for p in Payment.objects.filter(preorder=preorder, status="POSTED")
        ) or Decimal("0.00")
        if net >= preorder.quantity * preorder.agreed_unit_price:
            PreOrder.objects.filter(pk=preorder.pk).update(
                settled_at=preorder.fulfilled_at or preorder.created_at
            )

    cancelled = PreOrder.objects.filter(status="CANCELLED")
    cancelled.filter(cancelled_at__isnull=True).update(cancelled_at=F("created_at"))
    cancelled.filter(cancelled_by__isnull=True).update(cancelled_by=F("created_by"))
    cancelled.filter(cancellation_reason="").update(cancellation_reason=LEGACY_REASON)


class Migration(migrations.Migration):
    dependencies = [
        ("preorders", "0003_order_number_seq"),
        ("sales", "0005_grant_record_payment"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
