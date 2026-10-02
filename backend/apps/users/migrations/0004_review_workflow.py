from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0003_compliance_identity_fields')]
    operations = [
        migrations.AddField('pilotprofile', 'id_card_no', models.CharField(blank=True, default='', max_length=32)),
        migrations.AddField('pilotprofile', 'license_no', models.CharField(blank=True, default='', max_length=64)),
        migrations.AddField('pilotprofile', 'id_card_front_url', models.URLField(blank=True, default='')),
        migrations.AddField('pilotprofile', 'id_card_back_url', models.URLField(blank=True, default='')),
        migrations.AddField('pilotprofile', 'license_document_url', models.URLField(blank=True, default='')),
        migrations.AddField('pilotprofile', 'insurance_document_url', models.URLField(blank=True, default='')),
        migrations.AddField('pilotprofile', 'aircraft_document_url', models.URLField(blank=True, default='')),
        migrations.AddField('pilotprofile', 'review_status', models.CharField(choices=[('draft','待完善'),('pending','待审核'),('approved','已通过'),('rejected','已驳回')], default='draft', max_length=20)),
        migrations.AddField('pilotprofile', 'review_reason', models.TextField(blank=True, default='')),
        migrations.AddField('pilotprofile', 'submitted_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('pilotprofile', 'reviewed_at', models.DateTimeField(blank=True, null=True)),
    ]
