from decimal import Decimal

from rest_framework import serializers
from apps.common.dates import weekday_zh
from .models import DroneDevice, MaintenanceRecord, RentalOrder


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False,
    )

    class Meta:
        model = MaintenanceRecord
        fields = '__all__'


class DroneDeviceSerializer(serializers.ModelSerializer):
    maintenances = MaintenanceRecordSerializer(many=True, read_only=True)
    daily_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    monthly_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    deposit = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    depreciation = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    stock = serializers.IntegerField(min_value=0, required=False)

    class Meta:
        model = DroneDevice
        fields = '__all__'


class RentalOrderSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.model_name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    device_detail = DroneDeviceSerializer(source='device', read_only=True)
    start_weekday = serializers.SerializerMethodField()
    end_weekday = serializers.SerializerMethodField()

    class Meta:
        model = RentalOrder
        fields = '__all__'
        read_only_fields = [
            'order_no', 'user', 'deposit_paid', 'deposit_waived', 'insurance_fee',
            'rent_amount', 'status', 'damage_fee', 'credit_score_snapshot',
            'start_weekday', 'end_weekday',
        ]

    def get_start_weekday(self, obj):
        return weekday_zh(obj.start_date)

    def get_end_weekday(self, obj):
        return weekday_zh(obj.end_date)

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': '结束日期不能早于开始日期。'})
        return attrs
