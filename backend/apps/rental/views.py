from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.models import UserAccount

from .models import DroneDevice, MaintenanceRecord, RentalOrder
from .serializers import (
    DroneDeviceSerializer,
    MaintenanceRecordSerializer,
    RentalOrderSerializer,
)


INSURANCE_DAILY = Decimal('38.00')


def is_admin_user(user):
    return (
        user
        and user.is_authenticated
        and (
            user.role == UserAccount.Role.ADMIN
            or user.is_staff
        )
    )


class DroneDeviceViewSet(viewsets.ModelViewSet):
    queryset = DroneDevice.objects.prefetch_related(
        'maintenances'
    ).all()
    serializer_class = DroneDeviceSerializer
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly
    ]

    def get_permissions(self):
        if self.action in (
            'create',
            'update',
            'partial_update',
            'destroy',
            'add_maintenance',
        ):
            return [permissions.IsAuthenticated()]

        return super().get_permissions()

    def require_admin(
        self,
        request,
        message='仅管理员可以管理设备。',
    ):
        if not is_admin_user(request.user):
            return Response(
                {'detail': message},
                status=status.HTTP_403_FORBIDDEN,
            )

        return None

    def create(self, request, *args, **kwargs):
        denied = self.require_admin(
            request,
            '仅管理员可以上架设备。',
        )

        if denied:
            return denied

        return super().create(
            request,
            *args,
            **kwargs,
        )

    def update(self, request, *args, **kwargs):
        denied = self.require_admin(
            request,
            '仅管理员可以修改设备。',
        )

        if denied:
            return denied

        return super().update(
            request,
            *args,
            **kwargs,
        )

    def partial_update(self, request, *args, **kwargs):
        denied = self.require_admin(
            request,
            '仅管理员可以修改设备。',
        )

        if denied:
            return denied

        return super().partial_update(
            request,
            *args,
            **kwargs,
        )

    def destroy(self, request, *args, **kwargs):
        denied = self.require_admin(
            request,
            '仅管理员可以删除设备。',
        )

        if denied:
            return denied

        return super().destroy(
            request,
            *args,
            **kwargs,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='maintenance',
    )
    def add_maintenance(self, request, pk=None):
        denied = self.require_admin(
            request,
            '仅管理员可以录入维修。',
        )

        if denied:
            return denied

        with transaction.atomic():
            device = (
                DroneDevice.objects
                .select_for_update()
                .get(pk=pk)
            )

            rec = MaintenanceRecord.objects.create(
                device=device,
                content=request.data.get(
                    'content',
                    '',
                ),
                cost=request.data.get(
                    'cost',
                    0,
                ),
            )

            device.status = DroneDevice.Status.MAINTAINING
            device.save(
                update_fields=['status']
            )

        return Response(
            MaintenanceRecordSerializer(rec).data
        )


class RentalOrderViewSet(viewsets.ModelViewSet):
    queryset = RentalOrder.objects.select_related(
        'device',
        'user',
    ).all()
    serializer_class = RentalOrderSerializer
    permission_classes = [
        permissions.IsAuthenticated
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if is_admin_user(user):
            return qs

        return qs.filter(user=user)

    def create(self, request, *args, **kwargs):
        if request.user.role not in (
            UserAccount.Role.ENTERPRISE,
            UserAccount.Role.PILOT,
        ):
            return Response(
                {'detail': '仅企业用户或飞手可以租赁设备。'},
                status=status.HTTP_403_FORBIDDEN,
            )

        device_id = request.data.get('device')
        start = request.data.get('start_date')
        end = request.data.get('end_date')

        delivery = request.data.get(
            'delivery_type',
            RentalOrder.DeliveryType.PICKUP,
        )

        try:
            device = DroneDevice.objects.get(
                id=device_id
            )
        except DroneDevice.DoesNotExist:
            return Response(
                {'detail': '设备不存在。'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if (
            device.stock <= 0
            or device.status != DroneDevice.Status.AVAILABLE
        ):
            return Response(
                {'detail': '库存不足或设备不可租。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_d = date.fromisoformat(start)
            end_d = date.fromisoformat(end)
        except (TypeError, ValueError):
            return Response(
                {'detail': '租赁日期格式错误。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if end_d < start_d:
            return Response(
                {
                    'detail': (
                        '结束日期不能早于开始日期。'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        days = max(
            (end_d - start_d).days + 1,
            1,
        )

        # 租期 >= 28 天按月租估算
        if days >= 28:
            months = max(days // 30, 1)
            rent = device.monthly_price * months
        else:
            rent = device.daily_price * days

        credit = request.user.credit_score

        waive = (
            credit
            >= settings.CREDIT_WAIVE_DEPOSIT_SCORE
        )

        deposit = (
            Decimal('0')
            if waive
            else device.deposit
        )

        insurance = INSURANCE_DAILY * days

        # 时间 + UUID，避免同一秒创建多个订单时 order_no 冲突
        order_no = (
            f"RL{timezone.now().strftime('%Y%m%d%H%M%S')}"
            f"{uuid4().hex[:16]}"
        )

        try:
            order = RentalOrder.objects.create(
                order_no=order_no,
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
                remark=request.data.get(
                    'remark',
                    '',
                ),
            )
        except IntegrityError:
            # 极低概率 UUID 冲突时重新生成订单号
            order_no = (
                f"RL{timezone.now().strftime('%Y%m%d%H%M%S')}"
                f"{uuid4().hex[:16]}"
            )

            order = RentalOrder.objects.create(
                order_no=order_no,
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
                remark=request.data.get(
                    'remark',
                    '',
                ),
            )

        return Response(
            RentalOrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """
        支付租金 + 保险 + 押金。

        并发安全：
        1. 锁定 RentalOrder，防止同一订单重复支付。
        2. 锁定 DroneDevice，防止多个订单同时扣减同一设备库存。
        3. 订单状态、库存、设备状态在同一个事务中完成。
        """

        with transaction.atomic():
            try:
                order = (
                    self.get_queryset()
                    .select_for_update()
                    .get(pk=pk)
                )
            except RentalOrder.DoesNotExist:
                return Response(
                    {'detail': '租赁订单不存在。'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if order.status != RentalOrder.Status.PENDING_PAY:
                return Response(
                    {
                        'detail': (
                            '订单当前状态不可支付。'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                device = (
                    DroneDevice.objects
                    .select_for_update()
                    .get(pk=order.device_id)
                )
            except DroneDevice.DoesNotExist:
                return Response(
                    {'detail': '租赁设备不存在。'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if (
                device.stock <= 0
                or device.status
                != DroneDevice.Status.AVAILABLE
            ):
                return Response(
                    {
                        'detail': (
                            '设备库存不足或设备已不可租。'
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # 在设备锁持有期间扣减库存
            device.stock -= 1

            if device.stock == 0:
                device.status = DroneDevice.Status.RENTED

            device.save(
                update_fields=[
                    'stock',
                    'status',
                ]
            )

            # 与库存修改处于同一个事务
            order.status = RentalOrder.Status.RENTING
            order.save(
                update_fields=['status']
            )

        return Response(
            {
                'order': RentalOrderSerializer(
                    order
                ).data,
                'paid_total': float(
                    order.rent_amount
                    + order.insurance_fee
                    + order.deposit_paid
                ),
                'deposit_waived': (
                    order.deposit_waived
                ),
                'credit_tip': (
                    '信用达标，已免押金'
                    if order.deposit_waived
                    else '已收取设备押金'
                ),
            }
        )

    @action(detail=True, methods=['post'])
    def return_device(self, request, pk=None):
        """
        租客申请归还。

        只允许：
            RENTING -> RETURNING

        防止重复点击导致状态异常。
        """

        with transaction.atomic():
            try:
                order = (
                    self.get_queryset()
                    .select_for_update()
                    .get(pk=pk)
                )
            except RentalOrder.DoesNotExist:
                return Response(
                    {'detail': '租赁订单不存在。'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if order.status != RentalOrder.Status.RENTING:
                return Response(
                    {
                        'detail': (
                            '当前状态不可申请归还。'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order.status = RentalOrder.Status.RETURNING
            order.save(
                update_fields=['status']
            )

        return Response(
            RentalOrderSerializer(order).data
        )

    @action(detail=True, methods=['post'])
    def inspect(self, request, pk=None):
        """
        归还验机。

        - 无损坏：退押金
        - 有损坏：扣维修费
        - 恢复设备库存
        - 必要时创建维修记录

        所有数据库写操作在一个事务中完成。

        只有管理员可以验机，租赁用户只能提交归还申请。
        """

        if not is_admin_user(request.user):
            return Response(
                {'detail': '仅管理员可以进行设备验机。'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            damage_fee = Decimal(
                str(
                    request.data.get(
                        'damage_fee',
                        0,
                    )
                )
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):
            return Response(
                {
                    'detail': (
                        'damage_fee 格式错误。'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if damage_fee < 0:
            return Response(
                {
                    'detail': (
                        'damage_fee 不能小于 0。'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                order = (
                    RentalOrder.objects
                    .select_for_update()
                    .select_related('device')
                    .get(pk=pk)
                )
            except RentalOrder.DoesNotExist:
                return Response(
                    {'detail': '租赁订单不存在。'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # 防止重复验机导致库存重复增加
            if order.status != RentalOrder.Status.RETURNING:
                return Response(
                    {
                        'detail': (
                            '当前订单状态不可验机。'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 锁住设备，保证库存更新安全
            device = (
                DroneDevice.objects
                .select_for_update()
                .get(pk=order.device_id)
            )

            refund = max(
                order.deposit_paid - damage_fee,
                Decimal('0'),
            )

            order.damage_fee = damage_fee
            order.status = RentalOrder.Status.SETTLED
            order.remark = (
                (order.remark or '')
                + f' | 验机退押金 {refund}'
            )

            order.save(
                update_fields=[
                    'damage_fee',
                    'status',
                    'remark',
                ]
            )

            # 恢复库存
            device.stock = F('stock') + 1

            if damage_fee > 0:
                device.depreciation = (
                    F('depreciation')
                    + damage_fee
                )

            # 有损坏进入维修状态，否则恢复可租
            device.status = (
                DroneDevice.Status.MAINTAINING
                if damage_fee > 0
                else DroneDevice.Status.AVAILABLE
            )

            device.save(
                update_fields=[
                    'stock',
                    'depreciation',
                    'status',
                ]
            )

            if damage_fee > 0:
                MaintenanceRecord.objects.create(
                    device=device,
                    content=(
                        '租赁归还损伤维修，'
                        f'订单 {order.order_no}'
                    ),
                    cost=damage_fee,
                )

            # F() 表达式写入后刷新对象，
            # 保证返回数据准确
            device.refresh_from_db()

        order.refresh_from_db()

        return Response(
            {
                'order': RentalOrderSerializer(
                    order
                ).data,
                'deposit_refund': float(refund),
                'damage_fee': float(damage_fee),
            }
        )
