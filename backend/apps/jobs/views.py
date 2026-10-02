from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.common.permissions import is_admin_user
from apps.users.models import UserAccount

from .models import (
    JobPost,
    JobApplication,
    ChatMessage,
    LaborContract,
    AgencyFee,
)

from .serializers import (
    JobPostSerializer,
    JobApplicationSerializer,
    ChatMessageSerializer,
    LaborContractSerializer,
    AgencyFeeSerializer,
)


from .selectors import visible_job_applications, visible_job_posts
from .services import ai_match_score, create_job_post, recommend_pilots


class JobPostViewSet(viewsets.ModelViewSet):
    queryset = JobPost.objects.select_related('enterprise').all()
    serializer_class = JobPostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return visible_job_posts(
            user=self.request.user,
            action=self.action,
            mine=self.request.query_params.get('mine') == '1',
            status_value=self.request.query_params.get('status'),
        )

    def perform_create(self, serializer):
        user = self.request.user

        if user.role != UserAccount.Role.ENTERPRISE:
            raise PermissionDenied(
                '只有企业用户可以发布招聘岗位。'
            )

        serializer.instance = create_job_post(
            enterprise=user,
            validated_data=serializer.validated_data,
        )

    def perform_update(self, serializer):
        """
        只有岗位所属企业或管理员可以修改岗位。

        岗位状态业务上只允许：
            OPEN -> OPEN
            OPEN -> CLOSED

        CLOSED -> OPEN 应由业务层禁止。
        """

        job = self.get_object()
        user = self.request.user

        if not is_admin_user(user):
            if job.enterprise_id != user.id:
                raise PermissionDenied(
                    '只能修改自己的招聘岗位。'
                )

        serializer.save()

    def perform_destroy(self, instance):
        """
        只有岗位所属企业或管理员可以删除岗位。
        """

        user = self.request.user

        if not is_admin_user(user):
            if instance.enterprise_id != user.id:
                raise PermissionDenied(
                    '只能删除自己的招聘岗位。'
                )

        instance.delete()

    def _ai_recommend(self, job: JobPost):
        return recommend_pilots(job=job)

    @action(detail=True, methods=['post'])
    def recommend(self, request, pk=None):
        """
        手动触发 AI 推荐。

        只有岗位所属企业或管理员可以操作。
        岗位必须处于 OPEN 状态。
        """

        job = self.get_object()

        if not is_admin_user(request.user):
            if job.enterprise_id != request.user.id:
                return Response(
                    {'detail': '只能操作自己的招聘岗位。'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if job.status != JobPost.Status.OPEN:
            return Response(
                {
                    'detail': (
                        '岗位已关闭，不能继续进行 AI 推荐。'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        self._ai_recommend(job)

        apps = job.applications.filter(
            source=JobApplication.Source.AI
        )

        return Response(
            JobApplicationSerializer(
                apps,
                many=True,
            ).data
        )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """
        企业主动关闭岗位。
        """

        job = self.get_object()

        if not is_admin_user(request.user):
            if job.enterprise_id != request.user.id:
                return Response(
                    {'detail': '只能关闭自己的招聘岗位。'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if job.status == JobPost.Status.CLOSED:
            return Response(
                {
                    'detail': (
                        '该岗位已经关闭，无需重复操作。'
                    )
                },
                status=status.HTTP_200_OK,
            )

        job.status = JobPost.Status.CLOSED
        job.save(update_fields=['status'])

        return Response(
            JobPostSerializer(job).data,
            status=status.HTTP_200_OK,
        )


class JobApplicationViewSet(viewsets.ModelViewSet):
    queryset = (
        JobApplication.objects
        .select_related(
            'job',
            'pilot',
            'job__enterprise',
        )
        .prefetch_related('messages')
        .all()
    )

    serializer_class = JobApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return visible_job_applications(user=self.request.user)

    def perform_create(self, serializer):
        """
        飞手主动投递招聘岗位。

        业务规则：
        1. 只有飞手可以主动投递
        2. 岗位必须处于 OPEN
        3. 如果该飞手已经被 AI 推荐：
           RECOMMENDED -> APPLIED
           不创建新的 JobApplication
        4. 如果已经处于其他状态，则禁止重复投递
        5. 使用事务锁避免并发情况下重复创建
        """

        user = self.request.user

        if user.role != UserAccount.Role.PILOT:
            raise PermissionDenied(
                '只有飞手可以主动投递招聘岗位。'
            )
        profile = getattr(user, 'pilot_profile', None)
        if not profile or not profile.verified:
            reason = getattr(profile, 'review_reason', '') if profile else ''
            raise PermissionDenied(reason or '实名认证与飞行资质尚未审核通过，请先到个人中心补充资料。')

        job = serializer.validated_data['job']

        with transaction.atomic():
            # 锁住岗位，避免同时发生：
            # AI 推荐 + 飞手主动投递
            locked_job = (
                JobPost.objects
                .select_for_update()
                .get(pk=job.pk)
            )

            if locked_job.status != JobPost.Status.OPEN:
                raise ValidationError(
                    {
                        'job': (
                            '该岗位已经关闭，无法投递。'
                        )
                    }
                )

            # 查找当前飞手对该岗位已有的申请
            application = (
                JobApplication.objects
                .select_for_update()
                .filter(
                    job=locked_job,
                    pilot=user,
                )
                .first()
            )

            # 已经存在申请
            if application is not None:

                # AI 推荐 -> 飞手主动投递
                if (
                    application.status
                    == JobApplication.Status.RECOMMENDED
                ):
                    score = application.match_score

                    if (
                        score is None
                        and hasattr(user, 'pilot_profile')
                    ):
                        score = ai_match_score(
                            locked_job,
                            user.pilot_profile,
                        )

                    application.status = (
                        JobApplication.Status.APPLIED
                    )
                    application.source = (
                        JobApplication.Source.SELF
                    )

                    if score is not None:
                        application.match_score = score

                    application.save(
                        update_fields=[
                            'status',
                            'source',
                            'match_score',
                        ]
                    )

                    # 关键修复：
                    # 当前 serializer 是 CreateModelMixin
                    # 创建流程，需要知道实际返回的 instance
                    serializer.instance = application
                    return

                if (
                    application.status
                    == JobApplication.Status.APPLIED
                ):
                    raise ValidationError(
                        {
                            'job': (
                                '你已经申请过这个岗位，'
                                '不能重复投递。'
                            )
                        }
                    )

                if (
                    application.status
                    == JobApplication.Status.INTERVIEW
                ):
                    raise ValidationError(
                        {
                            'job': (
                                '你已经进入该岗位的面试流程。'
                            )
                        }
                    )

                if (
                    application.status
                    == JobApplication.Status.OFFERED
                ):
                    raise ValidationError(
                        {
                            'job': (
                                '该岗位已经向你发出 Offer。'
                            )
                        }
                    )

                if (
                    application.status
                    == JobApplication.Status.HIRED
                ):
                    raise ValidationError(
                        {
                            'job': (
                                '你已经被该岗位录用，'
                                '不能重复投递。'
                            )
                        }
                    )

                if (
                    application.status
                    == JobApplication.Status.REJECTED
                ):
                    raise ValidationError(
                        {
                            'job': (
                                '你此前已被该岗位拒绝，'
                                '不能重复投递。'
                            )
                        }
                    )

            # 没有任何申请记录 -> 创建新的主动申请
            score = 60.0

            if hasattr(user, 'pilot_profile'):
                score = ai_match_score(
                    locked_job,
                    user.pilot_profile,
                )

            application = JobApplication.objects.create(
                job=locked_job,
                pilot=user,
                match_score=score,
                source=JobApplication.Source.SELF,
                status=JobApplication.Status.APPLIED,
            )

            # 关键修复：
            # 手动 create 后绑定 serializer.instance，
            # 确保 DRF 能正确返回创建结果
            serializer.instance = application

    def perform_update(self, serializer):
        """
        不允许普通用户通过 PUT/PATCH 直接修改申请状态。

        所有状态变化必须通过：
            chat
            sign-contract
            onboard
            以及未来专门的 reject 接口
        """

        user = self.request.user

        if not is_admin_user(user):
            raise PermissionDenied(
                '招聘申请状态不能直接修改，请通过业务流程操作。'
            )

        serializer.save()

    def perform_destroy(self, instance):
        """
        不允许普通用户直接删除招聘申请。
        管理员可以删除。
        """

        if not is_admin_user(self.request.user):
            raise PermissionDenied(
                '招聘申请不能直接删除。'
            )

        instance.delete()

    @action(detail=True, methods=['post'], url_path='schedule-interview')
    def schedule_interview(self, request, pk=None):
        app = self.get_object()
        if not (is_admin_user(request.user) or (request.user.role == UserAccount.Role.ENTERPRISE and app.job.enterprise_id == request.user.id)):
            return Response({'detail': '只有岗位所属企业可以安排面试。'}, status=403)
        if app.status not in (JobApplication.Status.RECOMMENDED, JobApplication.Status.APPLIED, JobApplication.Status.INTERVIEW):
            return Response({'detail': '当前申请状态不能安排面试。'}, status=400)
        interview_at = request.data.get('interview_at')
        if not interview_at:
            return Response({'detail': '请填写面试时间。'}, status=400)
        app.interview_at = interview_at
        app.interview_note = (request.data.get('interview_note') or '').strip()
        app.status = JobApplication.Status.INTERVIEW
        app.save(update_fields=['interview_at', 'interview_note', 'status', 'status_updated_at'])
        ChatMessage.objects.create(application=app, sender=request.user, content=f'面试安排：{interview_at} {app.interview_note}'.strip(), msg_type=ChatMessage.MsgType.INTERVIEW)
        return Response(JobApplicationSerializer(app, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        app = self.get_object()
        if not (is_admin_user(request.user) or (request.user.role == UserAccount.Role.ENTERPRISE and app.job.enterprise_id == request.user.id)):
            return Response({'detail': '只有岗位所属企业可以拒绝申请。'}, status=403)
        if app.status in (JobApplication.Status.HIRED, JobApplication.Status.REJECTED):
            return Response({'detail': '该申请已经结束。'}, status=400)
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'detail': '请填写拒绝原因。'}, status=400)
        app.status = JobApplication.Status.REJECTED
        app.rejection_reason = reason
        app.save(update_fields=['status', 'rejection_reason', 'status_updated_at'])
        return Response(JobApplicationSerializer(app, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def chat(self, request, pk=None):
        """
        招聘双方聊天。

        企业：
            - 可以发送普通消息
            - 可以发起面试

        飞手：
            - 可以发送普通消息
            - 不能单方面把状态改成 INTERVIEW
        """

        with transaction.atomic():
            app = (
                JobApplication.objects
                .select_for_update()
                .select_related(
                    'job',
                    'pilot',
                )
                .get(pk=pk)
            )

            user = request.user

            is_enterprise = (
                user.role == UserAccount.Role.ENTERPRISE
                and app.job.enterprise_id == user.id
            )

            is_pilot = (
                user.role == UserAccount.Role.PILOT
                and app.pilot_id == user.id
            )

            is_admin = is_admin_user(user)

            if not (is_enterprise or is_pilot or is_admin):
                return Response(
                    {'detail': '无权操作该招聘申请。'},
                    status=status.HTTP_403_FORBIDDEN,
                )

            content = request.data.get(
                'content',
                ''
            ).strip()

            if not content:
                return Response(
                    {'detail': '消息内容不能为空。'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            msg_type = request.data.get(
                'msg_type',
                ChatMessage.MsgType.TEXT,
            )

            if msg_type not in ChatMessage.MsgType.values:
                return Response(
                    {'detail': '无效的消息类型。'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 只有企业或管理员可以发起面试
            if msg_type == ChatMessage.MsgType.INTERVIEW:
                if not is_enterprise and not is_admin:
                    return Response(
                        {
                            'detail': (
                                '只有企业可以发起面试邀约。'
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

                # 只有 APPLIED / RECOMMENDED
                # 可以进入 INTERVIEW
                if app.status not in (
                    JobApplication.Status.RECOMMENDED,
                    JobApplication.Status.APPLIED,
                ):
                    return Response(
                        {
                            'detail': (
                                '当前申请状态不能发起面试邀约。'
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # 已入职 / 已拒绝的申请不能继续推进业务
            if app.status in (
                JobApplication.Status.HIRED,
                JobApplication.Status.REJECTED,
            ):
                return Response(
                    {
                        'detail': (
                            '该招聘申请已经结束，'
                            '不能继续推进业务流程。'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            msg = ChatMessage.objects.create(
                application=app,
                sender=user,
                content=content,
                msg_type=msg_type,
            )

            if msg_type == ChatMessage.MsgType.INTERVIEW:
                app.status = JobApplication.Status.INTERVIEW
                app.save(update_fields=['status'])

        return Response(
            ChatMessageSerializer(msg).data
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='sign-contract',
    )
    def sign_contract(self, request, pk=None):
        """
        合同签署。

        企业只能签 enterprise 一侧。
        飞手只能签 pilot 一侧。

        双方都签署之后：
            INTERVIEW -> OFFERED

        双方签完合同并不直接 HIRED。
        HIRED 必须由企业执行 onboard。
        """

        with transaction.atomic():
            app = (
                JobApplication.objects
                .select_for_update()
                .select_related(
                    'job',
                    'pilot',
                )
                .get(pk=pk)
            )

            user = request.user

            is_enterprise = (
                user.role == UserAccount.Role.ENTERPRISE
                and app.job.enterprise_id == user.id
            )

            is_pilot = (
                user.role == UserAccount.Role.PILOT
                and app.pilot_id == user.id
            )

            if not (is_enterprise or is_pilot):
                return Response(
                    {
                        'detail': (
                            '只有招聘双方可以签署合同。'
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if app.status not in (
                JobApplication.Status.INTERVIEW,
                JobApplication.Status.OFFERED,
            ):
                return Response(
                    {
                        'detail': (
                            '当前申请状态不能签署劳动合同。'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            contract, _ = LaborContract.objects.get_or_create(
                application=app,
                defaults={
                    'contract_content': (
                        f'劳务合同：'
                        f'{app.job.title} - '
                        f'{app.pilot.username}'
                    ),
                    'contract_url': (
                        f'/contracts/{app.id}.pdf'
                    ),
                },
            )

            # 防止重复签署
            if is_enterprise:
                if contract.signed_enterprise:
                    return Response(
                        {
                            'detail': (
                                '企业已经签署过该合同。'
                            ),
                            'contract': (
                                LaborContractSerializer(
                                    contract
                                ).data
                            ),
                        },
                        status=status.HTTP_200_OK,
                    )

                contract.signed_enterprise = True

            elif is_pilot:
                if contract.signed_pilot:
                    return Response(
                        {
                            'detail': (
                                '飞手已经签署过该合同。'
                            ),
                            'contract': (
                                LaborContractSerializer(
                                    contract
                                ).data
                            ),
                        },
                        status=status.HTTP_200_OK,
                    )

                contract.signed_pilot = True

            contract.save(
                update_fields=[
                    'signed_enterprise',
                    'signed_pilot',
                ]
            )

            # 双方签署完成 -> OFFERED
            if (
                contract.signed_enterprise
                and contract.signed_pilot
            ):
                app.status = JobApplication.Status.OFFERED
                app.save(update_fields=['status'])

        return Response(
            LaborContractSerializer(contract).data
        )

    @action(detail=True, methods=['post'])
    def onboard(self, request, pk=None):
        """
        企业确认入职。

        严格要求：
        1. 当前用户必须是该岗位企业或管理员
        2. 当前状态必须是 OFFERED
        3. 双方必须已经签署合同
        4. 不能重复入职

        成功后：
            OFFERED -> HIRED
        """

        with transaction.atomic():
            app = (
                JobApplication.objects
                .select_for_update()
                .select_related(
                    'job',
                    'pilot',
                )
                .get(pk=pk)
            )

            user = request.user

            if is_admin_user(user):
                is_authorized = True
            else:
                is_authorized = (
                    user.role == UserAccount.Role.ENTERPRISE
                    and app.job.enterprise_id == user.id
                )

            if not is_authorized:
                return Response(
                    {
                        'detail': (
                            '仅该岗位企业可以确认入职。'
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if app.status == JobApplication.Status.HIRED:
                return Response(
                    {
                        'detail': (
                            '该申请已经完成入职。'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if app.status != JobApplication.Status.OFFERED:
                return Response(
                    {
                        'detail': (
                            '只有双方签署合同后，'
                            '才能确认入职。'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                contract = (
                    LaborContract.objects
                    .select_for_update()
                    .get(application=app)
                )
            except LaborContract.DoesNotExist:
                return Response(
                    {
                        'detail': (
                            '合同不存在，无法确认入职。'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not (
                contract.signed_enterprise
                and contract.signed_pilot
            ):
                return Response(
                    {
                        'detail': (
                            '双方尚未完成合同签署，'
                            '不能确认入职。'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 正式完成入职
            app.status = JobApplication.Status.HIRED
            app.save(update_fields=['status'])

            contract.onboarded_at = timezone.now()
            contract.save(
                update_fields=['onboarded_at']
            )

            # 计算中介费
            mid = (
                app.job.salary_min
                + app.job.salary_max
            ) / 2

            rate = Decimal(
                str(settings.AGENCY_FEE_RATE)
            )

            amount = (
                Decimal(str(mid)) * rate
            ).quantize(
                Decimal('0.01')
            )

            fee, _ = AgencyFee.objects.update_or_create(
                application=app,
                defaults={
                    'fee_rate': rate,
                    'amount': amount,
                    'status': AgencyFee.Status.PAID,
                    'paid_at': timezone.now(),
                },
            )

        return Response(
            {
                'application': JobApplicationSerializer(
                    app
                ).data,
                'agency_fee': AgencyFeeSerializer(
                    fee
                ).data,
            }
        )
