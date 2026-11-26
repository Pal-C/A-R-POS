"""
Receipts now require ``sales.record_payment`` (stringing research R6).
Before that change any signed-in staff account could take payments, so
this grants the permission to every existing active user to keep the
counter working after deploy. Remove it from accounts that should not
take money.

Reverse is a no-op: it cannot tell which grants existed before.
"""

from django.db import migrations


def grant_record_payment(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("accounts", "User")

    # Permissions are normally created after migrations run; make sure
    # this one exists on a fresh database.
    content_type, _ = ContentType.objects.get_or_create(
        app_label="sales", model="payment"
    )
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename="record_payment",
        defaults={"name": "Can record payments"},
    )

    for user in User.objects.filter(is_active=True).iterator():
        user.user_permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0004_customer_protect"),
        ("accounts", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(grant_record_payment, migrations.RunPython.noop),
    ]
