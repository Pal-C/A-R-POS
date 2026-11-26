"""
Sequence for stringing order numbers (research R1).

``nextval()`` never hands out the same value twice, even across rolled-back
transactions, so order numbers are unique and never reused. The sequence
starts above the highest numeric suffix among existing ``STR-`` numbers.
"""

from django.db import migrations

CREATE = """
DO $$
DECLARE
    start_at bigint;
BEGIN
    SELECT COALESCE(MAX((substring(order_number FROM '([0-9]+)$'))::bigint), 0) + 1
      INTO start_at
      FROM stringing_stringingorder
     WHERE order_number ~ '^STR-.*[0-9]+$';
    EXECUTE format('CREATE SEQUENCE stringing_order_number_seq START WITH %s', start_at);
END $$;
"""

DROP = "DROP SEQUENCE IF EXISTS stringing_order_number_seq;"


class Migration(migrations.Migration):
    dependencies = [
        ("stringing", "0003_stringing_management"),
    ]

    operations = [
        migrations.RunSQL(CREATE, reverse_sql=DROP),
    ]
