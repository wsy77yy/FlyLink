from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0005_alter_workorder_budget_and_more')]
    operations = [
        migrations.AddField(model_name='workorder', name='airspace_approved', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='workorder', name='weather_safe', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='workorder', name='compliance_reviewed_at', field=models.DateTimeField(blank=True, null=True)),
    ]
