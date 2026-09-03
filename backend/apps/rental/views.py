from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.models import UserAccount
from .models import DroneDevice, MaintenanceRecord, RentalOrder
from .serializers import DroneDeviceSerializer, MaintenanceRecordSerializer, RentalOrderSerializer


INSURANCE_DAILY = Decimal('38.00')


def is_admin_user(user):
    return (
        user
        and user.is_authenticated
        and (user.role == UserAccount.Role.ADMIN or user.is_staff)
    )


class DroneDeviceViewSet(viewsets.ModelViewSet):
    queryset = DroneDevice.objects.prefetch_related('maintenances').all()
    serializer_class = DroneDeviceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'add_maintenance'):
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def require_admin(self, request, message='仅管理员可管理设备'):
        if not is_admin_user(request.user):
            return Response({'detail': message}, status=status.HTTP_403_FORBIDDEN)
        return None

    def create(self, request, *args, **kwargs):
        denied = self.require_admin(request, '仅管理员可上架设备')
        if denied:
            return denied
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        denied = self.require_admin(request, '仅管理员可修改设备')
        if denied:
            return denied
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        denied = self.require_admin(request, '仅管理员可修改设备')
        if denied:
            return denied
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        denied = self.require_admin(request, '仅管理员可删除设备')
        if denied:
            return denied
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='maintenance')
    def add_maintenance(self, request, pk=None):
        denied = self.require_admin(request, '仅管理员可录入维保')
        if denied:
            return denied

        device = self.get_object()
        rec = MaintenanceRecord.objects.create(
            device=device,
            content=request.data.get('content', ''),
            cost=request.data.get('cost', 0),
        )
        device.status = DroneDevice.Status.MAINTAINING
        device.save(update_fields=['status'])
        return Response(MaintenanceRecordSerializer(rec).data)


class RentalOrderViewSet(viewsets.ModelViewSet):
    queryset = RentalOrder.objects.select_related('device', 'user').all()
    serializer_class = RentalOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if is_admin_user(user):
            return qs
        return qs.filter(user=user)

    def create(self, request, *args, **kwargs):
        device_id = request.data.get('device')
        start = request.data.get('start_date')
        end = request.data.get('end_date')
        delivery = request.data.get('delivery_type', RentalOrder.DeliveryType.PICKUP)

        try:
            device = DroneDevice.objects.get(id=device_id)
        except DroneDevice.DoesNotExist:
            return Response({'detail': '设备不存在'}, status=status.HTTP_404_NOT_FOUND)

        if device.stock <= 0 or device.status != DroneDevice.Status.AVAILABLE:
            return Response({'detail': '库存不足或设备不可租'}, status=status.HTTP_400_BAD_REQUEST)

        from datetime import date

        try:
            start_d = date.fromisoformat(start)
            end_d = date.fromisoformat(end)
        except (TypeError, ValueError):
            return Response({'detail': '租赁日期格式不正确'}, status=status.HTTP_400_BAD_REQUEST)

        if end_d < start_d:
            return Response({'detail': '结束日期不能早于开始日期'}, status=status.HTTP_400_BAD_REQUEST)

        days = (end_d - start_d).days + 1

        # 租期 ≥ 28 天按月租估算
        if days >= 28:
            months = max(days // 30, 1)
            rent = device.monthly_price * months
        else:
            rent = device.daily_price * days

        credit = request.user.credit_score
        waive = credit >= settings.CREDIT_WAIVE_DEPOSIT_SCORE
        deposit = Decimal('0') if waive else device.deposit
        insurance = INSURANCE_DAILY * days

        order = RentalOrder.objects.create(
            order_no=f"RL{timezone.now().strftime('%Y%m%d%H%M%S')}",
            user=request.user,
            device=device,
            start_date=start_d,
            end_date=end_d,
            delivery_type=delivery,
            deposit_paid=deposit,
            deposit_waived=waive,
            insurance_fee=insurance,
            rent_amount=rent,
            status=RentalOrder.Status.PENDING_PAY,
            credit_score_snapshot=credit,
            remark=request.data.get('remark', ''),
        )
        return Response(RentalOrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """支付租金+保险(+押金)，信用达标免押。"""
        order = self.get_object()
        if order.status != RentalOrder.Status.PENDING_PAY:
            return Response({'detail': '状态不可支付'}, status=status.HTTP_400_BAD_REQUEST)

        order.status = RentalOrder.Status.RENTING
        order.save(update_fields=['status'])

        device = order.device
        device.stock = max(device.stock - 1, 0)
        if device.stock == 0:
            device.status = DroneDevice.Status.RENTED
        device.save()

        return Response({
            'order': RentalOrderSerializer(order).data,
            'paid_total': float(order.rent_amount + order.insurance_fee + order.deposit_paid),
            'deposit_waived': order.deposit_waived,
            'credit_tip': '微信支付分/芝麻信用达标，已免押' if order.deposit_waived else '已收取设备押金',
        })

    @action(detail=True, methods=['post'])
    def return_device(self, request, pk=None):
        order = self.get_object()

        if order.status != RentalOrder.Status.RENTING:
            return Response({'detail': '只有租赁中的订单可以申请归还'}, status=status.HTTP_400_BAD_REQUEST)

        order.status = RentalOrder.Status.RETURNING
        order.save(update_fields=['status'])
        return Response(RentalOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def inspect(self, request, pk=None):
        """归还核验：无损坏退押金，有损伤扣维修费。"""
        order = self.get_object()

        demo_self_inspection = getattr(settings, 'DEMO_ALLOW_SELF_INSPECTION', True)

        if not is_admin_user(request.user):
            if not demo_self_inspection:
                return Response({'detail': '仅管理员可验机结算'}, status=status.HTTP_403_FORBIDDEN)

        if order.status != RentalOrder.Status.RETURNING:
            return Response({'detail': '只有归还中的订单可以验机'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            damage_fee = Decimal(str(request.data.get('damage_fee', 0)))
        except (InvalidOperation, TypeError, ValueError):
            return Response({'detail': '损坏费用格式不正确'}, status=status.HTTP_400_BAD_REQUEST)

        if damage_fee < 0:
            return Response({'detail': '损坏费用不能为负数'}, status=status.HTTP_400_BAD_REQUEST)

        order.damage_fee = damage_fee
        refund = max(order.deposit_paid - damage_fee, Decimal('0'))
        order.status = RentalOrder.Status.SETTLED
        order.remark = (order.remark or '') + f' | 核验退押金 {refund}'
        order.save()

        device = order.device
        device.stock += 1
        device.status = DroneDevice.Status.AVAILABLE

        if damage_fee > 0:
            device.depreciation += damage_fee
            MaintenanceRecord.objects.create(
                device=device,
                content=f'租赁归还损伤维修，订单 {order.order_no}',
                cost=damage_fee,
            )

        device.save()

        return Response({
            'order': RentalOrderSerializer(order).data,
            'deposit_refund': float(refund),
            'damage_fee': float(damage_fee),
        })
