from decimal import Decimal

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.users.models import UserAccount
from .models import WorkOrder, OrderMatchLog, FlightPlan, WorkTrack, WorkMedia, Settlement
from .serializers import (
    WorkOrderSerializer, OrderMatchLogSerializer, FlightPlanSerializer,
    WorkTrackSerializer, WorkMediaSerializer, SettlementSerializer,
)
from .services import smart_match_and_push, gen_order_no


def is_admin_user(user):
    return (
        user
        and user.is_authenticated
        and (user.role == UserAccount.Role.ADMIN or user.is_staff)
    )


class WorkOrderViewSet(viewsets.ModelViewSet):
    queryset = WorkOrder.objects.select_related('enterprise', 'pilot').prefetch_related('medias').all()
    serializer_class = WorkOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        scope = self.request.query_params.get('scope')
        status_q = self.request.query_params.get('status')

        if status_q:
            qs = qs.filter(status=status_q)

        if not user.is_authenticated:
            return qs.none()

        if is_admin_user(user):
            return qs

        # 飞手接单时，只能看到无人接单且处于可接单状态的订单
        if self.action == 'accept':
            if user.role == UserAccount.Role.PILOT:
                return qs.filter(
                    status__in=[WorkOrder.Status.PENDING, WorkOrder.Status.MATCHED],
                    pilot__isnull=True,
                )
            return qs.none()

        # 企业侧操作：只允许操作自己发布的订单
        if self.action in ('update', 'partial_update', 'destroy', 'rematch', 'accept_delivery'):
            if user.role == UserAccount.Role.ENTERPRISE:
                return qs.filter(enterprise=user)
            return qs.none()

        # 飞手侧作业操作：只允许操作自己承接的订单
        if self.action in ('declare_flight', 'start_work', 'upload_track', 'upload_media', 'submit_work'):
            if user.role == UserAccount.Role.PILOT:
                return qs.filter(pilot=user)
            return qs.none()

        # 进度查看：企业、飞手只能查看与自己有关的订单
        if self.action == 'progress':
            if user.role == UserAccount.Role.ENTERPRISE:
                return qs.filter(enterprise=user)
            if user.role == UserAccount.Role.PILOT:
                return qs.filter(pilot=user)
            return qs.none()

        # 我的订单
        if scope == 'mine':
            if user.role == UserAccount.Role.ENTERPRISE:
                return qs.filter(enterprise=user)
            if user.role == UserAccount.Role.PILOT:
                return qs.filter(pilot=user)
            return qs.none()

        # 抢单大厅：飞手只能看到待匹配 / 已推送且尚未有人接单的订单
        if scope == 'hall' and user.role == UserAccount.Role.PILOT:
            return qs.filter(
                status__in=[WorkOrder.Status.PENDING, WorkOrder.Status.MATCHED],
                pilot__isnull=True,
            )

        # 默认可见范围：
        # 企业看自己发布的订单；
        # 飞手看自己承接的订单 + 可接单大厅订单；
        # 其他角色不给默认数据。
        if user.role == UserAccount.Role.ENTERPRISE:
            return qs.filter(enterprise=user)

        if user.role == UserAccount.Role.PILOT:
            return qs.filter(
                Q(pilot=user)
                | Q(status__in=[WorkOrder.Status.PENDING, WorkOrder.Status.MATCHED], pilot__isnull=True)
            )

        return qs.none()

    def perform_create(self, serializer):
        if self.request.user.role != UserAccount.Role.ENTERPRISE:
            raise PermissionDenied('仅企业用户可发布需求订单')

        order = serializer.save(
            enterprise=self.request.user,
            order_no=gen_order_no(),
            escrow_amount=serializer.validated_data['budget'],
            platform_fee_rate=Decimal(str(settings.PLATFORM_FEE_RATE)),
        )
        smart_match_and_push(order)

    def require_enterprise_owner_or_admin(self, request, order, message='仅发单企业可操作'):
        if is_admin_user(request.user):
            return None
        if order.enterprise_id != request.user.id:
            return Response({'detail': message}, status=status.HTTP_403_FORBIDDEN)
        return None

    def require_pilot_owner_or_admin(self, request, order, message='仅承接飞手可操作'):
        if is_admin_user(request.user):
            return None
        if order.pilot_id != request.user.id:
            return Response({'detail': message}, status=status.HTTP_403_FORBIDDEN)
        return None

    @action(detail=True, methods=['post'])
    def rematch(self, request, pk=None):
        order = self.get_object()

        denied = self.require_enterprise_owner_or_admin(request, order, '仅发单企业可重新匹配')
        if denied:
            return denied

        logs = smart_match_and_push(order)
        return Response(OrderMatchLogSerializer(logs, many=True).data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """飞手一键抢单。"""
        if request.user.role != UserAccount.Role.PILOT:
            return Response({'detail': '仅飞手可接单'}, status=status.HTTP_403_FORBIDDEN)

        order = self.get_object()

        if order.status not in [WorkOrder.Status.PENDING, WorkOrder.Status.MATCHED]:
            return Response({'detail': '订单状态不可接单'}, status=status.HTTP_400_BAD_REQUEST)

        if order.pilot_id:
            return Response({'detail': '已被他人接单'}, status=status.HTTP_400_BAD_REQUEST)

        order.pilot = request.user
        order.status = WorkOrder.Status.ACCEPTED
        order.assigned_by_admin = False
        order.save()

        request.user.pilot_profile.online_status = 'busy'
        request.user.pilot_profile.save(update_fields=['online_status'])

        # 自动生成飞行计划草稿
        FlightPlan.objects.get_or_create(
            order=order,
            defaults={
                'plan_content': {
                    'work_type': order.work_type,
                    'location': order.location,
                    'lat': float(order.lat) if order.lat else None,
                    'lng': float(order.lng) if order.lng else None,
                    'execute_time': order.execute_time.isoformat(),
                    'area_or_duration': order.area_or_duration,
                    'pilot': request.user.username,
                    'license': request.user.pilot_profile.license_level,
                }
            },
        )
        return Response(WorkOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """平台管理员指派飞手。"""
        if not is_admin_user(request.user):
            return Response({'detail': '仅管理员可指派'}, status=status.HTTP_403_FORBIDDEN)

        order = self.get_object()
        pilot_id = request.data.get('pilot_id')

        try:
            pilot = UserAccount.objects.get(id=pilot_id, role=UserAccount.Role.PILOT)
        except UserAccount.DoesNotExist:
            return Response({'detail': '飞手不存在'}, status=status.HTTP_404_NOT_FOUND)

        order.pilot = pilot
        order.status = WorkOrder.Status.ACCEPTED
        order.assigned_by_admin = True
        order.save()

        FlightPlan.objects.get_or_create(
            order=order,
            defaults={
                'plan_content': {
                    'work_type': order.work_type,
                    'location': order.location,
                    'execute_time': order.execute_time.isoformat(),
                    'pilot': pilot.username,
                    'assigned': True,
                }
            },
        )
        return Response(WorkOrderSerializer(order).data)

    @action(detail=True, methods=['post'], url_path='declare')
    def declare_flight(self, request, pk=None):
        """一键提交空域飞行计划申报（对接模拟接口）。"""
        order = self.get_object()

        denied = self.require_pilot_owner_or_admin(request, order, '仅承接飞手可提交飞行申报')
        if denied:
            return denied

        plan, _ = FlightPlan.objects.get_or_create(order=order, defaults={'plan_content': {}})
        plan.declare_status = FlightPlan.DeclareStatus.SUBMITTED
        plan.external_ref = f'AIR-{order.order_no}'
        plan.plan_content = {
            **(plan.plan_content or {}),
            'submitted_at': timezone.now().isoformat(),
            'api': 'mock-airspace-declare',
            'result': 'accepted',
        }
        plan.save()

        order.status = WorkOrder.Status.DECLARED
        order.save(update_fields=['status', 'updated_at'])

        # 模拟批复
        plan.declare_status = FlightPlan.DeclareStatus.APPROVED
        plan.save(update_fields=['declare_status'])
        return Response(FlightPlanSerializer(plan).data)

    @action(detail=True, methods=['post'])
    def start_work(self, request, pk=None):
        order = self.get_object()

        denied = self.require_pilot_owner_or_admin(request, order, '仅承接飞手可开始作业')
        if denied:
            return denied

        order.status = WorkOrder.Status.WORKING
        order.save(update_fields=['status', 'updated_at'])
        return Response(WorkOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def upload_track(self, request, pk=None):
        order = self.get_object()

        denied = self.require_pilot_owner_or_admin(request, order, '仅承接飞手可上传轨迹')
        if denied:
            return denied

        points = request.data.get('points') or [request.data]
        created = []

        for p in points:
            t = WorkTrack.objects.create(
                order=order,
                lat=p['lat'],
                lng=p['lng'],
                altitude=p.get('altitude', 0),
            )
            created.append(t)

        # 简易面积：轨迹点数 * 0.05 公顷模拟
        order.actual_area = Decimal(str(round(len(order.tracks.all()) * 0.05, 2)))
        order.save(update_fields=['actual_area', 'updated_at'])
        return Response(WorkTrackSerializer(created, many=True).data)

    @action(detail=True, methods=['post'])
    def upload_media(self, request, pk=None):
        order = self.get_object()

        denied = self.require_pilot_owner_or_admin(request, order, '仅承接飞手可上传成果影像')
        if denied:
            return denied

        media = WorkMedia.objects.create(
            order=order,
            media_type=request.data.get('media_type', 'image'),
            url=request.data.get('url', ''),
        )
        return Response(WorkMediaSerializer(media).data)

    @action(detail=True, methods=['post'])
    def submit_work(self, request, pk=None):
        order = self.get_object()

        denied = self.require_pilot_owner_or_admin(request, order, '仅承接飞手可提交作业')
        if denied:
            return denied

        order.status = WorkOrder.Status.SUBMITTED
        order.save(update_fields=['status', 'updated_at'])
        return Response(WorkOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def accept_delivery(self, request, pk=None):
        """甲方验收 → 生成托管结算并打款。"""
        order = self.get_object()

        denied = self.require_enterprise_owner_or_admin(request, order, '仅发单企业可验收')
        if denied:
            return denied

        order.status = WorkOrder.Status.ACCEPTED_DONE
        order.save(update_fields=['status', 'updated_at'])

        total = order.budget
        fee = (total * order.platform_fee_rate).quantize(Decimal('0.01'))
        income = total - fee

        settlement, _ = Settlement.objects.update_or_create(
            order=order,
            defaults={
                'total_amount': total,
                'platform_fee': fee,
                'pilot_income': income,
                'status': Settlement.Status.HOLDING,
            },
        )

        # 自动打款
        settlement.status = Settlement.Status.PAID
        settlement.paid_at = timezone.now()
        settlement.save()

        order.status = WorkOrder.Status.SETTLED
        order.save(update_fields=['status', 'updated_at'])

        if order.pilot and hasattr(order.pilot, 'pilot_profile'):
            order.pilot.pilot_profile.online_status = 'idle'
            order.pilot.pilot_profile.save(update_fields=['online_status'])

        return Response(SettlementSerializer(settlement).data)

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        order = self.get_object()
        return Response({
            'order': WorkOrderSerializer(order).data,
            'tracks': WorkTrackSerializer(order.tracks.all(), many=True).data,
            'medias': WorkMediaSerializer(order.medias.all(), many=True).data,
            'flight_plan': FlightPlanSerializer(order.flight_plan).data if hasattr(order, 'flight_plan') else None,
            'settlement': SettlementSerializer(order.settlement).data if hasattr(order, 'settlement') else None,
        })
