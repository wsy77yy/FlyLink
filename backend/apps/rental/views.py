from rest_framework import permissions, status, viewsets
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.permissions import IsAdminRole, IsRentalCustomer

from .models import DroneModel, DroneUnit, RentalOrder
from .selectors import drone_models, visible_rental_orders
from .serializers import (
    DroneModelSerializer,
    DroneUnitSerializer,
    MaintenanceRecordSerializer,
    RentalOrderSerializer,
)
from .services import (
    RentalDomainError,
    add_maintenance,
    add_unit,
    create_drone_model,
    create_rental_order,
    inspect_return,
    parse_damage_fee,
    pay_rental_order,
    request_return,
    update_drone_model,
)


class ServiceErrorMixin:
    def service_response(self, callback, *args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except RentalDomainError as exc:
            return Response({'detail': exc.message}, status=exc.status_code)


class DroneModelViewSet(ServiceErrorMixin, viewsets.ModelViewSet):
    queryset = drone_models()
    serializer_class = DroneModelSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        if self.action in {
            'create', 'update', 'partial_update', 'destroy',
            'add_unit', 'add_maintenance',
        }:
            return [IsAdminRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.instance = create_drone_model(validated_data=serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = update_drone_model(
            model=serializer.instance,
            validated_data=serializer.validated_data,
        )

    @action(detail=True, methods=['post'], url_path='units')
    def add_unit(self, request, pk=None):
        model = self.get_object()
        serializer = DroneUnitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = add_unit(
            model=model,
            serial_number=serializer.validated_data.get('serial_number'),
        )
        return Response(DroneUnitSerializer(unit).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='maintenance')
    def add_maintenance(self, request, pk=None):
        model = self.get_object()
        unit_id = request.data.get('unit_id')
        unit = model.units.filter(pk=unit_id).first() if unit_id else None
        if unit is None:
            return Response(
                {'detail': '请提供属于该型号的有效 unit_id。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MaintenanceRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = add_maintenance(
            unit=unit,
            content=serializer.validated_data['content'],
            cost=serializer.validated_data.get('cost', 0),
        )
        return Response(MaintenanceRecordSerializer(record).data)


# Preserve the historical router/view import name used by the frontend URL module.
DroneDeviceViewSet = DroneModelViewSet


class RentalOrderViewSet(ServiceErrorMixin, viewsets.ModelViewSet):
    queryset = RentalOrder.objects.all()
    serializer_class = RentalOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return visible_rental_orders(user=self.request.user)

    def create(self, request, *args, **kwargs):
        if not IsRentalCustomer().has_permission(request, self):
            return Response(
                {'detail': IsRentalCustomer.message},
                status=status.HTTP_403_FORBIDDEN,
            )
        if request.user.role == 'pilot':
            profile = getattr(request.user, 'pilot_profile', None)
            if not profile or not profile.verified:
                reason = getattr(profile, 'review_reason', '') if profile else ''
                return Response({'detail': reason or '实名认证与飞行资质尚未审核通过，请先补充资料。'}, status=403)
        delivery = request.data.get('delivery_type', RentalOrder.DeliveryType.PICKUP)
        if delivery not in RentalOrder.DeliveryType.values:
            return Response({'detail': '取件方式无效。'}, status=status.HTTP_400_BAD_REQUEST)
        result = self.service_response(
            create_rental_order,
            user=request.user,
            model_id=request.data.get('device'),
            start=request.data.get('start_date'),
            end=request.data.get('end_date'),
            delivery_type=delivery,
            remark=request.data.get('remark', ''),
            delivery_address=request.data.get('delivery_address', ''),
        )
        if isinstance(result, Response):
            return result
        return Response(RentalOrderSerializer(result).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.service_response(
            pay_rental_order,
            order_id=pk,
            queryset=self.get_queryset(),
        )
        if isinstance(order, Response):
            return order
        return Response({
            'order': RentalOrderSerializer(order).data,
            'paid_total': float(order.rent_amount + order.insurance_fee + order.deposit_paid),
            'deposit_waived': order.deposit_waived,
            'credit_tip': '信用达标，已免押金' if order.deposit_waived else '已收取设备押金',
        })

    @action(detail=True, methods=['post'])
    def return_device(self, request, pk=None):
        order = self.service_response(
            request_return,
            order_id=pk,
            queryset=self.get_queryset(),
        )
        if isinstance(order, Response):
            return order
        return Response(RentalOrderSerializer(order).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminRole])
    def inspect(self, request, pk=None):
        try:
            damage_fee = parse_damage_fee(request.data.get('damage_fee', 0))
        except RentalDomainError as exc:
            return Response({'detail': exc.message}, status=exc.status_code)
        result = self.service_response(
            inspect_return,
            order_id=pk,
            damage_fee=damage_fee,
        )
        if isinstance(result, Response):
            return result
        order, refund = result
        return Response({
            'order': RentalOrderSerializer(order).data,
            'deposit_refund': float(refund),
            'damage_fee': float(damage_fee),
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_queryset().filter(pk=pk).select_related('unit').first()
        if not order:
            return Response({'detail': '租赁订单不存在。'}, status=404)
        if order.status != RentalOrder.Status.PENDING_PAY:
            return Response({'detail': '只有待支付订单可以取消。'}, status=400)
        order.status = RentalOrder.Status.CANCELLED
        order.cancel_reason = (request.data.get('reason') or '用户取消').strip()
        order.cancelled_at = timezone.now()
        order.save(update_fields=['status', 'cancel_reason', 'cancelled_at'])
        order.unit.status = DroneUnit.Status.AVAILABLE
        order.unit.save(update_fields=['status'])
        return Response(RentalOrderSerializer(order).data)
