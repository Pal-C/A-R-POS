from django.db import migrations

from customers.phone import normalize_phone


def backfill(apps, schema_editor):
    """Fills Customer.phone_normalized for rows created before the column existed."""
    Customer = apps.get_model("customers", "Customer")
    to_update = []

    for customer in Customer.objects.only("id", "phone_number").iterator():
        customer.phone_normalized = normalize_phone(customer.phone_number)
        to_update.append(customer)

    Customer.objects.bulk_update(to_update, ["phone_normalized"], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0002_phone_normalized_audit_events"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
