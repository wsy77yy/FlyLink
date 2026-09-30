from django.db.models import Q

from apps.common.permissions import is_admin_user
from apps.users.models import UserAccount

from .models import WorkOrder


ENTERPRISE_ACTIONS = {
    'update', 'partial_update', 'destroy', 'rematch', 'accept_delivery',
    'pay_deposit', 'pay_balance', 'cancel_order',
}
PILOT_ACTIONS = {
    'declare_flight', 'start_work', 'upload_track', 'upload_media',
    'submit_work', 'arrive', 'finish_work',
}
OPEN_STATUSES = (WorkOrder.Status.PENDING, WorkOrder.Status.MATCHED)


def work_order_queryset():
    return (
        WorkOrder.objects
        .select_related(
            'enterprise', 'enterprise__enterprise_profile', 'pilot',
            'flight_plan', 'settlement',
        )
        .prefetch_related('medias')
    )


def visible_work_orders(*, user, action, scope=None, status_value=None):
    qs = work_order_queryset()
    if status_value:
        qs = qs.filter(status=status_value)
    if not user.is_authenticated:
        return qs.none()
    if is_admin_user(user):
        return qs
    if action == 'accept':
        return qs.filter(status__in=OPEN_STATUSES, pilot__isnull=True) \
            if user.role == UserAccount.Role.PILOT else qs.none()
    if action in ENTERPRISE_ACTIONS:
        return qs.filter(enterprise=user) \
            if user.role == UserAccount.Role.ENTERPRISE else qs.none()
    if action in PILOT_ACTIONS:
        return qs.filter(pilot=user) \
            if user.role == UserAccount.Role.PILOT else qs.none()
    if action == 'progress' or scope == 'mine':
        if user.role == UserAccount.Role.ENTERPRISE:
            return qs.filter(enterprise=user)
        if user.role == UserAccount.Role.PILOT:
            return qs.filter(pilot=user)
        return qs.none()
    if scope == 'hall' and user.role == UserAccount.Role.PILOT:
        return qs.filter(status__in=OPEN_STATUSES, pilot__isnull=True)
    if user.role == UserAccount.Role.ENTERPRISE:
        return qs.filter(enterprise=user)
    if user.role == UserAccount.Role.PILOT:
        return qs.filter(
            Q(pilot=user) | Q(status__in=OPEN_STATUSES, pilot__isnull=True),
        )
    return qs.none()
