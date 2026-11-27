"""Backfill Sale.sale_date for finalized sales (specs/006-sales-ui R3).

The business date is the store-local date of ``finalized_at`` (falling back to
``created_at``). Drafts keep a null sale_date.
"""

from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import migrations


def backfill_sale_date(apps, schema_editor):
    Sale = apps.get_model("sales", "Sale")
    store_tz = ZoneInfo(settings.STORE_TIME_ZONE)
    pending = Sale.objects.exclude(status="DRAFT").filter(sale_date__isnull=True)
    for sale in pending.only("pk", "finalized_at", "created_at").iterator():
        moment = sale.finalized_at or sale.created_at
        Sale.objects.filter(pk=sale.pk).update(sale_date=moment.astimezone(store_tz).date())


class Migration(migrations.Migration):
    dependencies = [("sales", "0006_sale_sale_date_saleevent")]

    operations = [migrations.RunPython(backfill_sale_date, migrations.RunPython.noop)]
