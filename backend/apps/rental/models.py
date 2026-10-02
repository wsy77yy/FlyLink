from django.db import models
from django.utils import timezone

from apps.users.models import UserAccount


class DroneModel(models.Model):
    """Commercial/catalog data shared by physical drones of the same model."""

    model_name = models.CharField(max_length=128, unique=True)
    specs = models.JSONField(default=dict, blank=True)
    daily_price = models.DecimalField(max_digits=10, decimal_places=2)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    deposit = models.DecimalField(max_digits=10, decimal_places=2)
    cover_image = models.URLField(blank=True, default='')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'drone_model'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(daily_price__gte=0, monthly_price__gte=0, deposit__gte=0),
                name='drone_model_prices_nonnegative',
            ),
        ]


class DroneUnit(models.Model):
    """A single traceable physical drone."""

    class Status(models.TextChoices):
        AVAILABLE = 'available', '可租'
        RESERVED = 'reserved', '待支付锁定'
        RENTED = 'rented', '出租中'
        MAINTAINING = 'maintaining', '维保中'
        RETIRED = 'retired', '已退役'

    model = models.ForeignKey(DroneModel, on_delete=models.PROTECT, related_name='units')
    serial_number = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    depreciation = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    acquired_at = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'drone_unit'
        ordering = ['serial_number']
        constraints = [
            models.CheckConstraint(
                check=models.Q(depreciation__gte=0),
                name='drone_unit_depreciation_nonnegative',
            ),
        ]


class MaintenanceRecord(models.Model):
    unit = models.ForeignKey(DroneUnit, on_delete=models.CASCADE, related_name='maintenances')
    content = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    maintained_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'maintenance_record'
        ordering = ['-maintained_at']
        constraints = [
            models.CheckConstraint(check=models.Q(cost__gte=0), name='maintenance_cost_nonnegative'),
        ]


class RentalOrder(models.Model):
    class DeliveryType(models.TextChoices):
        PICKUP = 'pickup', '线下自提'
        EXPRESS = 'express', '物流配送'

    class Status(models.TextChoices):
        PENDING_PAY = 'pending_pay', '待支付'
        RENTING = 'renting', '租赁中'
        RETURNING = 'returning', '归还核验中'
        SETTLED = 'settled', '已结清'
        CANCELLED = 'cancelled', '已取消'

    order_no = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='rental_orders')
    unit = models.ForeignKey(DroneUnit, on_delete=models.PROTECT, related_name='rental_orders')
    start_date = models.DateField()
    end_date = models.DateField()
    delivery_type = models.CharField(max_length=20, choices=DeliveryType.choices, default=DeliveryType.PICKUP)
    deposit_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deposit_waived = models.BooleanField(default=False)
    insurance_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAY)
    damage_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit_score_snapshot = models.IntegerField(default=600)
    remark = models.TextField(blank=True, default='')
    delivery_address = models.CharField(max_length=255, blank=True, default='')
    paid_at = models.DateTimeField(null=True, blank=True)
    return_requested_at = models.DateTimeField(null=True, blank=True)
    inspected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True, default='')
    deposit_refund = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rental_order'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='rental_dates_ordered',
            ),
            models.CheckConstraint(
                check=models.Q(deposit_paid__gte=0, insurance_fee__gte=0, rent_amount__gte=0, damage_fee__gte=0, deposit_refund__gte=0),
                name='rental_amounts_nonnegative',
            ),
            models.CheckConstraint(
                check=models.Q(credit_score_snapshot__gte=300, credit_score_snapshot__lte=1000),
                name='rental_credit_score_300_1000',
            ),
        ]
