from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.users.models import UserAccount, PilotProfile
from .models import JobPost, JobApplication, ChatMessage, LaborContract, AgencyFee
from .serializers import (
    JobPostSerializer, JobApplicationSerializer, ChatMessageSerializer,
    LaborContractSerializer, AgencyFeeSerializer,
)


def is_admin_user(user):
    return (
        user
        and user.is_authenticated
        and (user.role == UserAccount.Role.ADMIN or user.is_staff)
    )


def ai_match_score(job: JobPost, pilot: PilotProfile) -> float:
    score = 50.0
    if job.license_req and job.license_req.lower() in (pilot.license_level or '').lower():
        score += 25
    elif not job.license_req:
        score += 10
    skill_set = set(pilot.skills or [])
    tag_set = set(job.tags or [])
    if skill_set and tag_set:
        overlap = len(skill_set & tag_set) / max(len(tag_set), 1)
        score += overlap * 25
    score += min(pilot.years_exp, 10) * 1.5
    return round(min(score, 100), 2)


class JobPostViewSet(viewsets.ModelViewSet):
    queryset = JobPost.objects.select_related('enterprise').all()
    serializer_class = JobPostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if self.request.query_params.get('status'):
            qs = qs.filter(status=self.request.query_params['status'])

        # 修改、删除、重新推荐，只允许岗位发布企业或管理员操作
        if self.action in ('update', 'partial_update', 'destroy', 'recommend'):
            if not user.is_authenticated:
                return qs.none()
            if is_admin_user(user):
                return qs
            if user.role == UserAccount.Role.ENTERPRISE:
                return qs.filter(enterprise=user)
            return qs.none()

        # 我的岗位
        if self.request.query_params.get('mine') == '1':
            if not user.is_authenticated:
                return qs.none()
            if is_admin_user(user):
                return qs
            if user.role == UserAccount.Role.ENTERPRISE:
                return qs.filter(enterprise=user)
            return qs.none()

        return qs

    def perform_create(self, serializer):
        if self.request.user.role != UserAccount.Role.ENTERPRISE:
            raise PermissionDenied('仅企业用户可发布岗位')

        job = serializer.save(enterprise=self.request.user)
        # 创建后自动 AI 推荐飞手给企业
        self._ai_recommend(job)

    def _ai_recommend(self, job: JobPost):
        pilots = PilotProfile.objects.select_related('user').all()[:50]
        for p in pilots:
            score = ai_match_score(job, p)
            if score < 55:
                continue
            JobApplication.objects.get_or_create(
                job=job,
                pilot=p.user,
                defaults={
                    'match_score': score,
                    'status': JobApplication.Status.RECOMMENDED,
                    'source': JobApplication.Source.AI,
                },
            )

    @action(detail=True, methods=['post'])
    def recommend(self, request, pk=None):
        job = self.get_object()

        if not is_admin_user(request.user) and job.enterprise_id != request.user.id:
            return Response({'detail': '仅岗位发布企业可重新推荐'}, status=status.HTTP_403_FORBIDDEN)

        self._ai_recommend(job)
        apps = job.applications.filter(source=JobApplication.Source.AI)
        return Response(JobApplicationSerializer(apps, many=True).data)


class JobApplicationViewSet(viewsets.ModelViewSet):
    queryset = JobApplication.objects.select_related('job', 'pilot', 'job__enterprise').prefetch_related('messages').all()
    serializer_class = JobApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            return qs.none()

        if is_admin_user(user):
            return qs

        if user.role == UserAccount.Role.PILOT:
            return qs.filter(pilot=user)

        if user.role == UserAccount.Role.ENTERPRISE:
            return qs.filter(job__enterprise=user)

        return qs.none()

    def perform_create(self, serializer):
        if self.request.user.role != UserAccount.Role.PILOT:
            raise PermissionDenied('仅飞手可以投递岗位')

        job = serializer.validated_data['job']
        pilot = self.request.user

        score = 60.0
        if hasattr(pilot, 'pilot_profile'):
            score = ai_match_score(job, pilot.pilot_profile)

        serializer.save(
            pilot=pilot,
            match_score=score,
            source=JobApplication.Source.SELF,
            status=JobApplication.Status.APPLIED,
        )

    def update(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response(
                {'detail': '申请状态请通过聊天、签约、入职流程变更'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response(
                {'detail': '申请状态请通过聊天、签约、入职流程变更'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response({'detail': '仅管理员可删除岗位申请'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def chat(self, request, pk=None):
        app = self.get_object()

        is_enterprise = app.job.enterprise_id == request.user.id
        is_pilot = app.pilot_id == request.user.id

        if not is_admin_user(request.user) and not (is_enterprise or is_pilot):
            return Response({'detail': '仅岗位企业或申请飞手可聊天'}, status=status.HTTP_403_FORBIDDEN)

        msg_type = request.data.get('msg_type', ChatMessage.MsgType.TEXT)

        # 面试邀请只能由企业或管理员发起，避免飞手自己把状态改成面试
        if msg_type == ChatMessage.MsgType.INTERVIEW and not (is_enterprise or is_admin_user(request.user)):
            return Response({'detail': '仅企业可发起面试邀请'}, status=status.HTTP_403_FORBIDDEN)

        msg = ChatMessage.objects.create(
            application=app,
            sender=request.user,
            content=request.data.get('content', ''),
            msg_type=msg_type,
        )

        if msg.msg_type == ChatMessage.MsgType.INTERVIEW:
            app.status = JobApplication.Status.INTERVIEW
            app.save(update_fields=['status'])

        return Response(ChatMessageSerializer(msg).data)

    @action(detail=True, methods=['post'], url_path='sign-contract')
    def sign_contract(self, request, pk=None):
        app = self.get_object()

        contract, _ = LaborContract.objects.get_or_create(
            application=app,
            defaults={
                'contract_content': f'劳务合同：{app.job.title} - {app.pilot.username}',
                'contract_url': f'/contracts/{app.id}.pdf',
            },
        )

        if request.user.role == UserAccount.Role.ENTERPRISE:
            if app.job.enterprise_id != request.user.id:
                return Response({'detail': '仅岗位发布企业可签署企业端合同'}, status=status.HTTP_403_FORBIDDEN)
            contract.signed_enterprise = True

        elif request.user.role == UserAccount.Role.PILOT:
            if app.pilot_id != request.user.id:
                return Response({'detail': '仅申请飞手可签署飞手端合同'}, status=status.HTTP_403_FORBIDDEN)
            contract.signed_pilot = True

        else:
            return Response({'detail': '仅岗位企业或申请飞手可签署合同'}, status=status.HTTP_403_FORBIDDEN)

        contract.save()

        if contract.signed_enterprise and contract.signed_pilot and app.status != JobApplication.Status.HIRED:
            app.status = JobApplication.Status.OFFERED
            app.save(update_fields=['status'])

        return Response(LaborContractSerializer(contract).data)

    @action(detail=True, methods=['post'])
    def onboard(self, request, pk=None):
        """入职确认 → 中介费结算。"""
        app = self.get_object()

        if not is_admin_user(request.user) and app.job.enterprise_id != request.user.id:
            return Response({'detail': '仅岗位发布企业可确认入职'}, status=status.HTTP_403_FORBIDDEN)

        app.status = JobApplication.Status.HIRED
        app.save(update_fields=['status'])

        contract, _ = LaborContract.objects.get_or_create(application=app)
        contract.onboarded_at = timezone.now()
        contract.signed_enterprise = True
        contract.signed_pilot = True
        contract.save()

        mid = (app.job.salary_min + app.job.salary_max) / 2
        rate = Decimal(str(settings.AGENCY_FEE_RATE))
        amount = (Decimal(str(mid)) * rate).quantize(Decimal('0.01'))

        fee, _ = AgencyFee.objects.update_or_create(
            application=app,
            defaults={
                'fee_rate': rate,
                'amount': amount,
                'status': AgencyFee.Status.PAID,
                'paid_at': timezone.now(),
            },
        )

        return Response({
            'application': JobApplicationSerializer(app).data,
            'agency_fee': AgencyFeeSerializer(fee).data,
        })
