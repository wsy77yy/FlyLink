from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('rental', '0004_drone_model_and_unit')]
    operations = [
        migrations.AddField('rentalorder', 'delivery_address', models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField('rentalorder', 'paid_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('rentalorder', 'return_requested_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('rentalorder', 'inspected_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('rentalorder', 'cancelled_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('rentalorder', 'cancel_reason', models.TextField(blank=True, default='')),
        migrations.AddField('rentalorder', 'deposit_refund', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
        migrations.RemoveConstraint('rentalorder', 'rental_amounts_nonnegative'),
        migrations.AddConstraint('rentalorder', models.CheckConstraint(check=models.Q(deposit_paid__gte=0, insurance_fee__gte=0, rent_amount__gte=0, damage_fee__gte=0, deposit_refund__gte=0), name='rental_amounts_nonnegative')),
    ]
