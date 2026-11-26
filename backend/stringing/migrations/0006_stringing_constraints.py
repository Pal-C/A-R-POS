"""New stringing order constraints, added after the 0005 backfill."""

import django.db.models.functions.text
import django.db.models.lookups
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stringing", "0005_backfill_payment_state"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="stringingorder",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    django.db.models.lookups.GreaterThan(
                        django.db.models.functions.text.Length(
                            django.db.models.functions.text.Trim("racket_description")
                        ),
                        0,
                    )
                ),
                name="stringing_racket_not_blank",
            ),
        ),
        migrations.AddConstraint(
            model_name="stringingorder",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    django.db.models.lookups.GreaterThan(
                        django.db.models.functions.text.Length(
                            django.db.models.functions.text.Trim("string_type")
                        ),
                        0,
                    )
                ),
                name="stringing_string_type_not_blank",
            ),
        ),
        migrations.AddConstraint(
            model_name="stringingorder",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("cancelled_at__isnull", False),
                        ("cancelled_by__isnull", False),
                        ("status", "CANCELLED"),
                        models.Q(("cancellation_reason", ""), _negated=True),
                    ),
                    models.Q(
                        models.Q(("status", "CANCELLED"), _negated=True),
                        ("cancelled_at__isnull", True),
                        ("cancelled_by__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="stringing_cancel_fields_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="stringingorder",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("status", "COMPLETED"), _negated=True),
                    ("completed_at__isnull", False),
                    _connector="OR",
                ),
                name="stringing_completed_has_time",
            ),
        ),
    ]
