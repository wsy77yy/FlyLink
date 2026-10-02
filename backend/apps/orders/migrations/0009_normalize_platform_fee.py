from decimal import Decimal
from django.db import migrations


def normalize_fee(apps, schema_editor):
    apps.get_model('orders', 'WorkOrder').objects.update(platform_fee_rate=Decimal('0.1000'))


class Migration(migrations.Migration):
    dependencies = [('orders', '0008_workorder_abnormal_evidence_and_more')]
    operations = [migrations.RunPython(normalize_fee, migrations.RunPython.noop)]
