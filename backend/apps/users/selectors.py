from django.db.models import Q

from apps.common.permissions import is_admin_user

from .models import CreditReview, PilotProfile, PilotResume, UserAccount


def visible_pilot_profiles(*, user, action):
    qs = PilotProfile.objects.select_related('user')
    if action not in {'update', 'partial_update', 'destroy'}:
        return qs
    if not user.is_authenticated:
        return qs.none()
    if is_admin_user(user):
        return qs
    return qs.filter(user=user) if user.role == UserAccount.Role.PILOT else qs.none()


def visible_pilot_resumes(*, user, action, mine=False):
    qs = PilotResume.objects.select_related('pilot__user')
    restricted = action in {'update', 'partial_update', 'destroy'} or mine
    if not restricted:
        return qs
    if not user.is_authenticated:
        return qs.none()
    if is_admin_user(user):
        return qs
    if user.role == UserAccount.Role.PILOT and hasattr(user, 'pilot_profile'):
        return qs.filter(pilot=user.pilot_profile)
    return qs.none()


def visible_credit_reviews(*, user):
    qs = CreditReview.objects.select_related('from_user', 'to_user')
    if not user.is_authenticated:
        return qs.none()
    if is_admin_user(user):
        return qs
    return qs.filter(Q(from_user=user) | Q(to_user=user))
