from apps.common.permissions import is_admin_user
from apps.users.models import UserAccount

from .models import JobApplication, JobPost


def visible_job_posts(*, user, action, mine=False, status_value=None):
    qs = JobPost.objects.select_related('enterprise', 'enterprise__enterprise_profile')
    if status_value:
        qs = qs.filter(status=status_value)
    if action in {'update', 'partial_update', 'destroy', 'recommend', 'close'} or mine:
        if not user.is_authenticated:
            return qs.none()
        if is_admin_user(user):
            return qs
        return qs.filter(enterprise=user) \
            if user.role == UserAccount.Role.ENTERPRISE else qs.none()
    return qs


def visible_job_applications(*, user):
    qs = (
        JobApplication.objects
        .select_related(
            'job', 'pilot', 'job__enterprise', 'contract', 'agency_fee',
        )
        .prefetch_related('messages')
    )
    if not user.is_authenticated:
        return qs.none()
    if is_admin_user(user):
        return qs
    if user.role == UserAccount.Role.PILOT:
        return qs.filter(pilot=user)
    if user.role == UserAccount.Role.ENTERPRISE:
        return qs.filter(job__enterprise=user)
    return qs.none()
