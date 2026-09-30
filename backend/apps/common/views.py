from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.users.models import UserAccount
from apps.common.permissions import is_admin_user
from apps.orders.models import WorkOrder
from apps.rental.models import DroneModel, DroneUnit, RentalOrder
from apps.jobs.models import JobApplication, JobPost


@extend_schema(
    responses=inline_serializer(
        name='PlatformStats',
        fields={
            'order_count': serializers.IntegerField(),
            'pilot_count': serializers.IntegerField(),
            'enterprise_count': serializers.IntegerField(),
            'renting_device_count': serializers.IntegerField(),
            'open_jobs': serializers.IntegerField(),
            'device_total': serializers.IntegerField(),
            'device_model_count': serializers.IntegerField(),
        },
    ),
)
@api_view(['GET'])
@permission_classes([AllowAny])
def platform_stats(request):
    return Response({
        'order_count': WorkOrder.objects.count(),
        'pilot_count': UserAccount.objects.filter(role=UserAccount.Role.PILOT).count(),
        'enterprise_count': UserAccount.objects.filter(role=UserAccount.Role.ENTERPRISE).count(),
        'renting_device_count': DroneUnit.objects.filter(status=DroneUnit.Status.RENTED).count(),
        'open_jobs': JobPost.objects.filter(status=JobPost.Status.OPEN).count(),
        'device_total': DroneUnit.objects.count(),
        'device_model_count': DroneModel.objects.count(),
    })


@extend_schema(
    responses=inline_serializer(
        name='AdminStats',
        fields={
            name: serializers.IntegerField()
            for name in (
                'user_count', 'enterprise_count', 'pilot_count', 'order_count',
                'open_order_count', 'job_count', 'open_job_count',
                'application_count', 'device_total', 'device_model_count',
                'available_device_count', 'rental_order_count',
                'renting_device_count',
            )
        },
    ),
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_stats(request):
    """管理员工作台统计；普通企业和飞手不可访问。"""
    if not is_admin_user(request.user):
        return Response(
            {'detail': '仅管理员可以查看平台管理数据。'},
            status=403,
        )

    return Response({
        'user_count': UserAccount.objects.exclude(
            role=UserAccount.Role.ADMIN,
        ).count(),
        'enterprise_count': UserAccount.objects.filter(
            role=UserAccount.Role.ENTERPRISE,
        ).count(),
        'pilot_count': UserAccount.objects.filter(
            role=UserAccount.Role.PILOT,
        ).count(),
        'order_count': WorkOrder.objects.count(),
        'open_order_count': WorkOrder.objects.exclude(
            status__in=[
                WorkOrder.Status.SETTLED,
                WorkOrder.Status.CANCELLED,
            ],
        ).count(),
        'job_count': JobPost.objects.count(),
        'open_job_count': JobPost.objects.filter(
            status=JobPost.Status.OPEN,
        ).count(),
        'application_count': JobApplication.objects.count(),
        'device_total': DroneUnit.objects.count(),
        'device_model_count': DroneModel.objects.count(),
        'available_device_count': DroneUnit.objects.filter(
            status=DroneUnit.Status.AVAILABLE,
        ).count(),
        'rental_order_count': RentalOrder.objects.count(),
        'renting_device_count': RentalOrder.objects.filter(
            status=RentalOrder.Status.RENTING,
        ).count(),
    })
