from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0002_alter_creditreview_score_and_more')]
    operations = [
        migrations.AddField(model_name='useraccount', name='agreements_accepted_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='pilotprofile', name='insurance_expiry', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='pilotprofile', name='aircraft_registered', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='pilotprofile', name='aircraft_registration_no', field=models.CharField(blank=True, default='', max_length=64)),
    ]
