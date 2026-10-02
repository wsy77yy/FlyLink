from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0006_compliance_gates')]
    operations = [
        migrations.AddField('workorder', 'airspace_review_note', models.TextField(blank=True, default='')),
        migrations.AddField('workorder', 'weather_checked_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('workorder', 'airspace_valid_until', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('workorder', 'max_flight_altitude', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
    ]
