"""
Sequence for pre-order numbers (research R1). ``nextval()`` never repeats a
value, even across rolled-back transactions. Starts above the highest
numeric suffix among existing ``PO-`` numbers.
"""

from django.db import migrations

CREATE = """
DO $$
DECLARE
    start_at bigint;
BEGIN
    SELECT COALESCE(MAX((substring(order_number FROM '([0-9]+)$'))::bigint), 0) + 1
      INTO start_at
      FROM preorders_preorder
     WHERE order_number ~ '^PO-.*[0-9]+$';
    EXECUTE format('CREATE SEQUENCE preorder_number_seq START WITH %s', start_at);
END $$;
"""

DROP = "DROP SEQUENCE IF EXISTS preorder_number_seq;"


class Migration(migrations.Migration):
    dependencies = [
        ("preorders", "0002_preorder_management"),
    ]

    operations = [
        migrations.RunSQL(CREATE, reverse_sql=DROP),
    ]
