import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def split_devices(apps, schema_editor):
    DroneDevice = apps.get_model('rental', 'DroneDevice')
    DroneModel = apps.get_model('rental', 'DroneModel')
    DroneUnit = apps.get_model('rental', 'DroneUnit')
    RentalOrder = apps.get_model('rental', 'RentalOrder')
    MaintenanceRecord = apps.get_model('rental', 'MaintenanceRecord')

    for old in DroneDevice.objects.all().iterator():
        drone_model = DroneModel.objects.create(
            model_name=old.model_name,
            specs=old.specs,
            daily_price=old.daily_price,
            monthly_price=old.monthly_price,
            deposit=old.deposit,
            cover_image=old.cover_image,
            description=old.description,
        )
        orders = list(RentalOrder.objects.filter(device_id=old.pk).order_by('pk'))
        active_count = sum(
            order.status in {'pending_pay', 'renting', 'returning'}
            for order in orders
        )
        total_units = max(old.stock + active_count, 1)
        units = [
            DroneUnit.objects.create(
                model=drone_model,
                serial_number=f'LEGACY-{old.pk:04d}-{index:04d}',
                depreciation=old.depreciation if index == 1 else 0,
                acquired_at=timezone.localdate(),
            )
            for index in range(1, total_units + 1)
        ]
        available_index = 0
        for order in orders:
            if order.status in {'pending_pay', 'renting', 'returning'}:
                unit = units[available_index]
                available_index += 1
                unit.status = 'reserved' if order.status == 'pending_pay' else 'rented'
                unit.save(update_fields=['status'])
            else:
                unit = units[0]
            order.unit_id = unit.pk
            order.save(update_fields=['unit'])
        if old.status == 'maintaining' and not orders:
            units[0].status = 'maintaining'
            units[0].save(update_fields=['status'])
        for record in MaintenanceRecord.objects.filter(device_id=old.pk):
            record.unit_id = units[0].pk
            record.save(update_fields=['unit'])


class Migration(migrations.Migration):
    dependencies = [('rental', '0003_alter_rentalorder_credit_score_snapshot_and_more')]

    operations = [
        migrations.CreateModel(
            name='DroneModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model_name', models.CharField(max_length=128, unique=True)),
                ('specs', models.JSONField(blank=True, default=dict)),
                ('daily_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('monthly_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('deposit', models.DecimalField(decimal_places=2, max_digits=10)),
                ('cover_image', models.URLField(blank=True, default='')),
                ('description', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'drone_model',
                'ordering': ['-created_at'],
                'constraints': [
                    models.CheckConstraint(
                        check=models.Q(('daily_price__gte', 0), ('deposit__gte', 0), ('monthly_price__gte', 0)),
                        name='drone_model_prices_nonnegative',
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name='DroneUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('serial_number', models.CharField(max_length=64, unique=True)),
                ('status', models.CharField(choices=[('available', '可租'), ('reserved', '待支付锁定'), ('rented', '出租中'), ('maintaining', '维保中'), ('retired', '已退役')], default='available', max_length=20)),
                ('depreciation', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('acquired_at', models.DateField(default=timezone.localdate)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('model', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='units', to='rental.dronemodel')),
            ],
            options={
                'db_table': 'drone_unit',
                'ordering': ['serial_number'],
                'constraints': [
                    models.CheckConstraint(
                        check=models.Q(('depreciation__gte', 0)),
                        name='drone_unit_depreciation_nonnegative',
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name='maintenancerecord',
            name='unit',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='maintenances', to='rental.droneunit'),
        ),
        migrations.AddField(
            model_name='rentalorder',
            name='unit',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rental_orders', to='rental.droneunit'),
        ),
        migrations.RunPython(split_devices, migrations.RunPython.noop),
        migrations.RemoveField(model_name='maintenancerecord', name='device'),
        migrations.RemoveField(model_name='rentalorder', name='device'),
        migrations.AlterField(
            model_name='maintenancerecord',
            name='unit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='maintenances', to='rental.droneunit'),
        ),
        migrations.AlterField(
            model_name='rentalorder',
            name='unit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rental_orders', to='rental.droneunit'),
        ),
        migrations.DeleteModel(name='DroneDevice'),
    ]
