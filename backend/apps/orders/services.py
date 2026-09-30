import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Q

from apps.common.order_numbers import generate_order_no
from apps.users.models import PilotProfile

from .models import OrderMatchLog, WorkOrder, haversine_km


logger = logging.getLogger('flylink.orders')


def _license_ok(req: str, pilot_level: str) -> bool:
    if not req:
        return True
    return req.lower() in (pilot_level or '').lower() or (pilot_level or '') in req


def match_score(order: WorkOrder, pilot: PilotProfile, distance_km: float) -> float:
    """Calculate a score without issuing database queries."""
    distance_score = max(0, 100 - distance_km * 2)
    license_score = 100 if _license_ok(order.license_req, pilot.license_level) else 20
    review_avg = getattr(pilot, 'order_review_avg', None)
    review_score = (float(review_avg) if review_avg else 3.5) * 20
    online_score = {'idle': 100, 'busy': 30, 'offline': 0}.get(pilot.online_status, 0)
    return round(
        distance_score * 0.35
        + license_score * 0.25
        + review_score * 0.2
        + online_score * 0.2,
        2,
    )


def _candidate_pilots():
    annotation = Avg(
        'user__reviews_received__score',
        filter=Q(user__reviews_received__biz_type='order'),
    )
    pilots = list(
        PilotProfile.objects.select_related('user').filter(
            online_status__in=[PilotProfile.OnlineStatus.IDLE, PilotProfile.OnlineStatus.BUSY],
            verified=True,
        ).annotate(order_review_avg=annotation)
    )
    if pilots:
        return pilots
    return list(
        PilotProfile.objects.select_related('user').filter(
            online_status__in=PilotProfile.OnlineStatus.values,
        ).annotate(order_review_avg=annotation)
    )


@transaction.atomic
def smart_match_and_push(order: WorkOrder, limit: int = 20):
    candidates = []
    for pilot in _candidate_pilots():
        distance = haversine_km(order.lat, order.lng, pilot.lat, pilot.lng)
        if distance > order.match_radius_km and order.lat and pilot.lat:
            continue
        candidates.append((pilot, distance, match_score(order, pilot, distance)))

    pilot_ids = [pilot.user_id for pilot, _, _ in candidates]
    existing = {
        log.pilot_id: log
        for log in OrderMatchLog.objects.filter(order=order, pilot_id__in=pilot_ids)
    }
    new_logs = []
    changed_logs = []
    for pilot, distance, score in candidates:
        log = existing.get(pilot.user_id)
        if log:
            log.distance_km = distance
            log.score = score
            changed_logs.append(log)
        else:
            new_logs.append(OrderMatchLog(
                order=order,
                pilot=pilot.user,
                distance_km=distance,
                score=score,
            ))
    if new_logs:
        OrderMatchLog.objects.bulk_create(new_logs)
    if changed_logs:
        OrderMatchLog.objects.bulk_update(changed_logs, ['distance_km', 'score'])

    results = sorted([*new_logs, *changed_logs], key=lambda item: item.score, reverse=True)
    order.status = WorkOrder.Status.MATCHED
    order.escrow_amount = order.budget
    order.platform_fee_rate = Decimal(str(settings.PLATFORM_FEE_RATE))
    order.save(update_fields=['status', 'escrow_amount', 'platform_fee_rate', 'updated_at'])
    logger.info(
        'order_matched',
        extra={'order_no': order.order_no, 'candidate_count': len(results)},
    )
    return results[:limit]


def gen_order_no(prefix='WO'):
    return generate_order_no(prefix)


@transaction.atomic
def create_work_order(*, enterprise, validated_data):
    budget = validated_data['budget']
    order = WorkOrder.objects.create(
        enterprise=enterprise,
        order_no=gen_order_no(),
        escrow_amount=Decimal('0'),
        platform_fee_rate=Decimal(str(settings.PLATFORM_FEE_RATE)),
        deposit_amount=(budget * Decimal('0.20')).quantize(Decimal('0.01')),
        balance_amount=(budget * Decimal('0.80')).quantize(Decimal('0.01')),
        **validated_data,
    )
    smart_match_and_push(order)
    logger.info('order_created', extra={'order_no': order.order_no, 'user_id': enterprise.pk})
    return order
