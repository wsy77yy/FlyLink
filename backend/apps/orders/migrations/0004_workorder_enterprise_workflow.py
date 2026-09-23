from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0003_workorder_city_workorder_custom_work_type_and_more')]

    operations = [
        migrations.AddField(model_name='workorder', name='deposit_amount', field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.AddField(model_name='workorder', name='deposit_paid_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='balance_amount', field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.AddField(model_name='workorder', name='balance_paid_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='arrived_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='arrival_lat', field=models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True)),
        migrations.AddField(model_name='workorder', name='arrival_lng', field=models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True)),
        migrations.AddField(model_name='workorder', name='arrival_distance_km', field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='started_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='finished_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='submission_deadline', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='submitted_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='admin_reviewed_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='cancelled_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='workorder', name='cancellation_penalty', field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.AddField(model_name='workorder', name='cancel_reason', field=models.TextField(blank=True, default='')),
        migrations.AlterField(model_name='workorder', name='status', field=models.CharField(choices=[('pending', '待匹配'), ('matched', '已推送'), ('accepted', '已接单'), ('declared', '已申报'), ('arrived', '飞手已到达'), ('working', '作业中'), ('finished', '作业已完成'), ('submitted', '待验收'), ('reviewed', '管理员已审核'), ('accepted_done', '已验收'), ('settled', '已结算'), ('cancelled', '已取消')], default='pending', max_length=20)),
    ]
