from django.db.models import Count, Q, Sum

from apps.common.permissions import is_admin_user

from .models import DroneModel, DroneUnit, RentalOrder


def drone_models():
    return (
        DroneModel.objects
        .annotate(
            available_stock=Count(
                'units',
                filter=Q(units__status=DroneUnit.Status.AVAILABLE),
                distinct=True,
            ),
            total_depreciation=Sum('units__depreciation'),
        )
        .prefetch_related('units__maintenances')
    )


def visible_rental_orders(*, user):
    qs = RentalOrder.objects.select_related('unit__model', 'user').prefetch_related(
        'unit__maintenances', 'unit__model__units__maintenances',
    )
    return qs if is_admin_user(user) else qs.filter(user=user)
