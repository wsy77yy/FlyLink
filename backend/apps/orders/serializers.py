from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.common.dates import weekday_zh
from .models import WorkOrder, OrderMatchLog, FlightPlan, WorkTrack, WorkMedia, Settlement


class WorkMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkMedia
        fields = '__all__'


class WorkTrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkTrack
        fields = '__all__'


class FlightPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightPlan
        fields = '__all__'


class SettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settlement
        fields = '__all__'


class OrderMatchLogSerializer(serializers.ModelSerializer):
    pilot_name = serializers.CharField(source='pilot.username', read_only=True)

    class Meta:
        model = OrderMatchLog
        fields = '__all__'


class WorkOrderSerializer(serializers.ModelSerializer):
    enterprise_name = serializers.SerializerMethodField()
    pilot_name = serializers.CharField(source='pilot.username', read_only=True, default=None)
    work_type_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    distance_km = serializers.FloatField(read_only=True, required=False)
    medias = WorkMediaSerializer(many=True, read_only=True)
    flight_plan = FlightPlanSerializer(read_only=True)
    settlement = SettlementSerializer(read_only=True)
    execute_weekday = serializers.SerializerMethodField()
    match_radius_km = serializers.FloatField(min_value=0.1, max_value=1000, required=False)

    class Meta:
        model = WorkOrder
        fields = '__all__'
        read_only_fields = [
            'order_no', 'enterprise', 'pilot', 'status', 'assigned_by_admin',
            'escrow_amount', 'deposit_amount', 'balance_amount',
            'platform_fee_rate', 'cancellation_penalty', 'execute_weekday',
        ]

    def get_enterprise_name(self, obj):
        if hasattr(obj.enterprise, 'enterprise_profile'):
            return obj.enterprise.enterprise_profile.company_name
        return obj.enterprise.username

    def get_work_type_display(self, obj):
        return obj.work_type_label

    def get_execute_weekday(self, obj):
        value = timezone.localtime(obj.execute_time) if obj.execute_time else None
        return weekday_zh(value)

    def validate(self, attrs):
        work_type = attrs.get('work_type', getattr(self.instance, 'work_type', None))
        custom = attrs.get('custom_work_type', getattr(self.instance, 'custom_work_type', ''))
        if work_type == WorkOrder.WorkType.OTHER and not (custom or '').strip():
            raise serializers.ValidationError({'custom_work_type': '选择「其它」时请填写自定义作业类型'})

        execute_time = attrs.get('execute_time')
        if execute_time and execute_time <= timezone.now():
            raise serializers.ValidationError({'execute_time': '执行时间必须晚于当前时间。'})

        lat = attrs.get('lat', getattr(self.instance, 'lat', None))
        lng = attrs.get('lng', getattr(self.instance, 'lng', None))
        if lat is not None and not Decimal('-90') <= lat <= Decimal('90'):
            raise serializers.ValidationError({'lat': '纬度必须在 -90 到 90 之间。'})
        if lng is not None and not Decimal('-180') <= lng <= Decimal('180'):
            raise serializers.ValidationError({'lng': '经度必须在 -180 到 180 之间。'})
        return attrs
