from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('jobs', '0003_alter_jobpost_salary_max_alter_jobpost_salary_min_and_more')]
    operations = [
        migrations.AddField('jobapplication', 'interview_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('jobapplication', 'interview_note', models.TextField(blank=True, default='')),
        migrations.AddField('jobapplication', 'rejection_reason', models.TextField(blank=True, default='')),
        migrations.AddField('jobapplication', 'status_updated_at', models.DateTimeField(auto_now=True)),
    ]
