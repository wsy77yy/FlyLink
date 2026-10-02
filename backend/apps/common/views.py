from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.users.models import UserAccount, EnterpriseProfile, PilotProfile
from apps.common.permissions import is_admin_user
from apps.orders.models import WorkOrder, Settlement, WithdrawalRequest, InvoiceRequest
from apps.common.models import Notification, AuditLog, PlatformConfig
from apps.common.events import audit, notify
from apps.rental.models import DroneModel, DroneUnit, RentalOrder
from apps.jobs.models import JobApplication, JobPost, AgencyFee
from apps.users.serializers import UserSerializer
from apps.orders.serializers import WorkOrderSerializer


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


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def notifications(request):
    if request.method == 'POST':
        ids = request.data.get('ids') or []
        unread = Notification.objects.filter(user=request.user, read_at__isnull=True)
        if ids:
            unread = unread.filter(id__in=ids)
        return Response({'updated': unread.update(read_at=timezone.now())})
    orders = WorkOrder.objects.none()
    if request.user.role == UserAccount.Role.ENTERPRISE:
        orders = WorkOrder.objects.filter(enterprise=request.user)
    elif request.user.role == UserAccount.Role.PILOT:
        orders = WorkOrder.objects.filter(pilot=request.user)
    for order in orders.order_by('-updated_at')[:20]:
        notify(request.user, f'order-state-{order.id}-{order.status}', f'订单状态已更新：{order.get_status_display()}', f'{order.order_no} · {order.location}', f'/orders/{order.id}', 'order')
    profile = getattr(request.user, 'pilot_profile', None)
    if profile and (not profile.insurance_valid or not profile.aircraft_registered):
        notify(request.user, 'pilot-compliance', '合规资料待完善', '请检查执照、保险有效期、授权范围和航空器实名登记信息。', '/profile', 'compliance')
    return Response([{'id': item.id, 'type': item.category, 'title': item.title, 'content': item.content, 'created_at': item.created_at, 'link': item.link, 'unread': item.read_at is None} for item in Notification.objects.filter(user=request.user)[:100]])


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def finance_center(request):
    if request.method == 'POST':
        if request.user.role == UserAccount.Role.PILOT:
            item = WithdrawalRequest.objects.create(pilot=request.user, amount=request.data.get('amount'), account_hint=request.data.get('account_hint') or '模拟账户')
            notify(request.user, f'withdrawal-{item.id}', '提现申请已提交', '平台将在模拟审核后更新到账状态。', '/finance', 'finance')
        elif request.user.role == UserAccount.Role.ENTERPRISE:
            item = InvoiceRequest.objects.create(enterprise=request.user, amount=request.data.get('amount'), title=request.data.get('title') or '模拟企业抬头', tax_no=request.data.get('tax_no', ''))
            notify(request.user, f'invoice-{item.id}', '开票申请已提交', '电子发票将由管理员模拟开具。', '/finance', 'finance')
        else:
            return Response({'detail': '当前角色不能提交资金申请'}, status=403)
        audit(request.user, 'finance_request', item)
    settlements = Settlement.objects.select_related('order')
    if request.user.role == UserAccount.Role.PILOT:
        settlements = settlements.filter(order__pilot=request.user)
    elif request.user.role == UserAccount.Role.ENTERPRISE:
        settlements = settlements.filter(order__enterprise=request.user)
    elif not is_admin_user(request.user):
        settlements = settlements.none()
    return Response({'settlements': [{'order_no': x.order.order_no, 'total': x.total_amount, 'fee': x.platform_fee, 'income': x.pilot_income, 'status': x.status, 'paid_at': x.paid_at} for x in settlements], 'withdrawals': list(WithdrawalRequest.objects.filter(pilot=request.user).values()) if request.user.role == UserAccount.Role.PILOT else [], 'invoices': list(InvoiceRequest.objects.filter(enterprise=request.user).values()) if request.user.role == UserAccount.Role.ENTERPRISE else [], 'fee_rate': 0.10})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enterprise_certification(request):
    if request.user.role != UserAccount.Role.ENTERPRISE:
        return Response({'detail': '仅企业用户可提交企业认证'}, status=403)
    profile, _ = EnterpriseProfile.objects.get_or_create(user=request.user, defaults={'company_name': request.user.username + '企业'})
    for field in ('company_name', 'license_no', 'contact_name', 'address', 'legal_representative', 'business_license_url', 'legal_id_url'):
        if field in request.data:
            setattr(profile, field, request.data.get(field) or '')
    required = [profile.company_name, profile.license_no, profile.legal_representative, profile.business_license_url, profile.legal_id_url]
    if not all(required):
        return Response({'detail': '请完整填写企业名称、统一信用代码、法定代表人，并上传模拟营业执照与法人证件链接。'}, status=400)
    profile.review_status = EnterpriseProfile.ReviewStatus.PENDING
    profile.review_reason = ''
    profile.submitted_at = timezone.now()
    profile.save()
    return Response({'review_status': profile.review_status, 'detail': '企业认证资料已提交模拟审核。'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_finance_review(request, kind, item_id):
    if not is_admin_user(request.user):
        return Response({'detail': '仅管理员可审核'}, status=403)
    approved = bool(request.data.get('approved'))
    model = WithdrawalRequest if kind == 'withdrawal' else InvoiceRequest
    item = model.objects.get(pk=item_id)
    item.status = (WithdrawalRequest.Status.APPROVED if approved else WithdrawalRequest.Status.REJECTED) if kind == 'withdrawal' else (InvoiceRequest.Status.ISSUED if approved else InvoiceRequest.Status.REJECTED)
    item.review_note = request.data.get('reason', '')
    item.reviewed_at = timezone.now()
    if kind == 'invoice' and approved:
        item.invoice_url = f'https://mock.flylink.local/invoices/{item.id}.pdf'
    item.save()
    owner = item.pilot if kind == 'withdrawal' else item.enterprise
    notify(owner, f'{kind}-{item.id}-result', '资金申请审核已更新', item.get_status_display(), '/finance', 'finance')
    audit(request.user, f'{kind}_review', item, {'approved': approved})
    return Response({'id': item.id, 'status': item.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_pilot_policy(request, user_id):
    if not is_admin_user(request.user):
        return Response({'detail': '仅管理员可设置飞手权限'}, status=403)
    profile = PilotProfile.objects.get(user_id=user_id)
    if 'authorized_work_types' in request.data:
        profile.authorized_work_types = request.data['authorized_work_types'] or []
    if 'dispatch_suspended' in request.data:
        profile.dispatch_suspended = bool(request.data['dispatch_suspended'])
    if 'suspension_reason' in request.data:
        profile.suspension_reason = request.data['suspension_reason'] or ''
    if 'license_expiry' in request.data:
        profile.license_expiry = request.data['license_expiry'] or None
    profile.save()
    audit(request.user, 'pilot_policy_update', profile, {'suspended': profile.dispatch_suspended, 'scope': profile.authorized_work_types})
    return Response({'authorized_work_types': profile.authorized_work_types, 'dispatch_suspended': profile.dispatch_suspended, 'suspension_reason': profile.suspension_reason, 'license_expiry': profile.license_expiry})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_risk_config(request):
    if not is_admin_user(request.user):
        return Response({'detail': '仅管理员可设置风险规则'}, status=403)
    item, _ = PlatformConfig.objects.get_or_create(key='risk_rules', defaults={'value': {}})
    item.value = {
        'sensitive_keywords': request.data.get('sensitive_keywords') or ['机场', '军用', '禁飞', '政府'],
        'urgent_manual_review': bool(request.data.get('urgent_manual_review', True)),
        'weather_mode': 'simulated',
    }
    item.save()
    audit(request.user, 'risk_config_update', item, item.value)
    return Response(item.value)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_workspace(request):
    if not is_admin_user(request.user):
        return Response({'detail': '仅管理员可访问管理工作台'}, status=403)
    users = UserAccount.objects.exclude(role=UserAccount.Role.ADMIN).select_related('enterprise_profile', 'pilot_profile')
    user_rows = []
    for user in users:
        profile = getattr(user, 'enterprise_profile', None) or getattr(user, 'pilot_profile', None)
        user_rows.append({
            **UserSerializer(user).data,
            'verified': bool(getattr(profile, 'verified', False)),
            'display_name': getattr(profile, 'company_name', '') or getattr(profile, 'real_name', '') or user.username,
            'review_status': getattr(profile, 'review_status', 'approved' if getattr(profile, 'verified', False) else 'pending'),
            'review_reason': getattr(profile, 'review_reason', ''),
            'submitted_at': getattr(profile, 'submitted_at', None),
            'documents': ({
                '身份证正面': getattr(profile, 'id_card_front_url', ''),
                '身份证反面': getattr(profile, 'id_card_back_url', ''),
                '飞手执照': getattr(profile, 'license_document_url', ''),
                '保险凭证': getattr(profile, 'insurance_document_url', ''),
                '航空器登记': getattr(profile, 'aircraft_document_url', ''),
            } if user.role == UserAccount.Role.PILOT else {
                '营业执照': getattr(profile, 'business_license_url', ''),
                '法人证件': getattr(profile, 'legal_id_url', ''),
            }),
        })
    orders = WorkOrder.objects.select_related('enterprise', 'pilot').all()[:100]
    return Response({
        'users': user_rows,
        'orders': WorkOrderSerializer(orders, many=True, context={'request': request}).data,
        'finance': {
            'escrow_total': sum(order.escrow_amount for order in orders),
            'settled_count': sum(1 for order in orders if order.status == WorkOrder.Status.SETTLED),
            'pending_review_count': sum(1 for order in orders if order.status == WorkOrder.Status.SUBMITTED),
            'platform_fee_total': sum((item.platform_fee for item in Settlement.objects.all()), start=0),
            'pilot_income_total': sum((item.pilot_income for item in Settlement.objects.all()), start=0),
            'agency_fee_total': sum((item.amount for item in AgencyFee.objects.all()), start=0),
            'rental_income_total': sum((item.rent_amount + item.insurance_fee + item.damage_fee for item in RentalOrder.objects.exclude(status=RentalOrder.Status.CANCELLED)), start=0),
            'transactions': [{
                'order_no': order.order_no,
                'business': '作业订单',
                'amount': order.escrow_amount,
                'status': order.get_status_display(),
                'updated_at': order.updated_at,
            } for order in orders[:30]] + [{
                'order_no': item.order_no,
                'business': '设备租赁',
                'amount': item.rent_amount + item.insurance_fee + item.damage_fee,
                'status': item.get_status_display(),
                'updated_at': item.created_at,
            } for item in RentalOrder.objects.all()[:30]],
        },
        'alerts': [
            {'level': 'high' if order.status in (WorkOrder.Status.DISPUTED, WorkOrder.Status.ABORTED) else order.risk_level, 'title': order.get_status_display(), 'content': order.order_no + ' · ' + (order.abnormal_reason or order.review_reason or ', '.join(order.risk_flags)), 'link': f'/orders/{order.id}'}
            for order in WorkOrder.objects.filter(status__in=[WorkOrder.Status.PENDING_REVIEW, WorkOrder.Status.DISPUTED, WorkOrder.Status.ABORTED])[:30]
        ],
        'audit_logs': list(AuditLog.objects.values('action', 'target_type', 'target_id', 'detail', 'created_at')[:50]),
        'risk_config': PlatformConfig.objects.get_or_create(key='risk_rules', defaults={'value': {'sensitive_keywords': ['机场', '军用', '禁飞', '政府'], 'urgent_manual_review': True, 'weather_mode': 'simulated'}})[0].value,
        'withdrawals': list(WithdrawalRequest.objects.values()[:50]),
        'invoices': list(InvoiceRequest.objects.values()[:50]),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_verify_user(request, user_id):
    if not is_admin_user(request.user):
        return Response({'detail': '仅管理员可进行资质审核'}, status=403)
    try:
        account = UserAccount.objects.get(pk=user_id)
    except UserAccount.DoesNotExist:
        return Response({'detail': '用户不存在'}, status=404)
    profile = getattr(account, 'enterprise_profile', None) or getattr(account, 'pilot_profile', None)
    if not profile:
        return Response({'detail': '用户资质档案不存在'}, status=400)
    profile.verified = bool(request.data.get('verified', True))
    update_fields = ['verified']
    if hasattr(profile, 'review_status'):
        profile.review_status = profile.ReviewStatus.APPROVED if profile.verified else profile.ReviewStatus.REJECTED
        profile.review_reason = '' if profile.verified else (request.data.get('reason') or '资料未满足平台认证要求，请核对后重新提交。')
        profile.reviewed_at = timezone.now()
        update_fields += ['review_status', 'review_reason', 'reviewed_at']
    profile.save(update_fields=update_fields)
    notify(account, f'identity-review-{account.id}-{getattr(profile, "review_status", "")}', '实名认证审核' + ('通过' if profile.verified else '未通过'), getattr(profile, 'review_reason', '') or '认证已通过，可以使用对应业务功能。', '/profile', 'compliance')
    audit(request.user, 'identity_review', profile, {'verified': profile.verified, 'reason': getattr(profile, 'review_reason', '')})
    return Response({'id': account.id, 'verified': profile.verified, 'review_status': getattr(profile, 'review_status', ''), 'review_reason': getattr(profile, 'review_reason', '')})
