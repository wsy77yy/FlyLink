from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.users.models import UserAccount
from apps.orders.models import WorkOrder
from apps.rental.models import DroneDevice, RentalOrder
from apps.jobs.models import JobApplication, JobPost


@api_view(['GET'])
@permission_classes([AllowAny])
def platform_stats(request):
    return Response({
        'order_count': WorkOrder.objects.count(),
        'pilot_count': UserAccount.objects.filter(role=UserAccount.Role.PILOT).count(),
        'enterprise_count': UserAccount.objects.filter(role=UserAccount.Role.ENTERPRISE).count(),
        'renting_device_count': RentalOrder.objects.filter(status=RentalOrder.Status.RENTING).count()
        or DroneDevice.objects.filter(status=DroneDevice.Status.RENTED).count(),
        'open_jobs': JobPost.objects.filter(status=JobPost.Status.OPEN).count(),
        'device_total': DroneDevice.objects.count(),
    })


def _is_admin(user):
    return (
        user.is_authenticated
        and (user.role == UserAccount.Role.ADMIN or user.is_staff)
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_stats(request):
    """管理员工作台统计；普通企业和飞手不可访问。"""
    if not _is_admin(request.user):
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
        'device_total': DroneDevice.objects.count(),
        'available_device_count': DroneDevice.objects.filter(
            status=DroneDevice.Status.AVAILABLE,
        ).count(),
        'rental_order_count': RentalOrder.objects.count(),
        'renting_device_count': RentalOrder.objects.filter(
            status=RentalOrder.Status.RENTING,
        ).count(),
    })
