from decimal import Decimal

from rest_framework import serializers

from apps.common.dates import weekday_zh

from .models import DroneModel, DroneUnit, MaintenanceRecord, RentalOrder


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False,
    )

    class Meta:
        model = MaintenanceRecord
        fields = '__all__'
        read_only_fields = ['unit']


class DroneUnitSerializer(serializers.ModelSerializer):
    maintenances = MaintenanceRecordSerializer(many=True, read_only=True)
    serial_number = serializers.CharField(max_length=64, required=False)

    class Meta:
        model = DroneUnit
        fields = '__all__'
        read_only_fields = ['model', 'depreciation', 'created_at']


class DroneModelSerializer(serializers.ModelSerializer):
    units = DroneUnitSerializer(many=True, read_only=True)
    stock = serializers.IntegerField(min_value=0, required=False, write_only=True)
    status = serializers.SerializerMethodField()
    depreciation = serializers.SerializerMethodField()
    daily_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    monthly_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    deposit = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))

    class Meta:
        model = DroneModel
        fields = [
            'id', 'model_name', 'specs', 'daily_price', 'monthly_price',
            'deposit', 'stock', 'status', 'depreciation', 'cover_image',
            'description', 'created_at', 'units',
        ]

    def _available_stock(self, obj):
        if hasattr(obj, 'available_stock'):
            return obj.available_stock
        return sum(unit.status == DroneUnit.Status.AVAILABLE for unit in obj.units.all())

    def get_status(self, obj) -> str:
        if self._available_stock(obj):
            return DroneUnit.Status.AVAILABLE
        statuses = {unit.status for unit in obj.units.all()}
        if DroneUnit.Status.MAINTAINING in statuses:
            return DroneUnit.Status.MAINTAINING
        if DroneUnit.Status.RENTED in statuses or DroneUnit.Status.RESERVED in statuses:
            return DroneUnit.Status.RENTED
        return DroneUnit.Status.RETIRED

    def get_depreciation(self, obj) -> Decimal:
        if hasattr(obj, 'total_depreciation'):
            return obj.total_depreciation or Decimal('0')
        return sum((unit.depreciation for unit in obj.units.all()), Decimal('0'))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['stock'] = self._available_stock(instance)
        return data


# Compatibility import for clients and internal code during the model transition.
DroneDeviceSerializer = DroneModelSerializer


class RentalOrderSerializer(serializers.ModelSerializer):
    device = serializers.IntegerField(source='unit.model_id', read_only=True)
    device_name = serializers.CharField(source='unit.model.model_name', read_only=True)
    serial_number = serializers.CharField(source='unit.serial_number', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    device_detail = DroneModelSerializer(source='unit.model', read_only=True)
    unit_detail = DroneUnitSerializer(source='unit', read_only=True)
    start_weekday = serializers.SerializerMethodField()
    end_weekday = serializers.SerializerMethodField()

    class Meta:
        model = RentalOrder
        fields = '__all__'
        read_only_fields = [
            'order_no', 'user', 'unit', 'deposit_paid', 'deposit_waived',
            'insurance_fee', 'rent_amount', 'status', 'damage_fee',
            'credit_score_snapshot', 'start_weekday', 'end_weekday',
        ]

    def get_start_weekday(self, obj) -> str:
        return weekday_zh(obj.start_date)

    def get_end_weekday(self, obj) -> str:
        return weekday_zh(obj.end_date)
