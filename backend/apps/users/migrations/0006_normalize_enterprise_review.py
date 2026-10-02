from django.db import migrations


def normalize_review(apps, schema_editor):
    Profile = apps.get_model('users', 'EnterpriseProfile')
    Profile.objects.filter(verified=True).update(review_status='approved')


class Migration(migrations.Migration):
    dependencies = [('users', '0005_enterpriseprofile_business_license_url_and_more')]
    operations = [migrations.RunPython(normalize_review, migrations.RunPython.noop)]
