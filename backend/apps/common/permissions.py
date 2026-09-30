from rest_framework.permissions import BasePermission

from apps.users.models import UserAccount


def is_admin_user(user):
    return bool(
        user
        and user.is_authenticated
        and (user.role == UserAccount.Role.ADMIN or user.is_staff)
    )


class HasRole(BasePermission):
    roles = ()

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.roles
        )


class IsAdminRole(HasRole):
    message = '仅管理员可以执行此操作。'

    def has_permission(self, request, view):
        return is_admin_user(request.user)


class IsEnterpriseRole(HasRole):
    roles = (UserAccount.Role.ENTERPRISE,)
    message = '仅企业用户可以执行此操作。'


class IsPilotRole(HasRole):
    roles = (UserAccount.Role.PILOT,)
    message = '仅飞手可以执行此操作。'


class IsRentalCustomer(HasRole):
    roles = (UserAccount.Role.ENTERPRISE, UserAccount.Role.PILOT)
    message = '仅企业用户或飞手可以租赁设备。'
