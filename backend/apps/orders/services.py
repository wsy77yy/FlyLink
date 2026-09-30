from decimal import Decimal
from django.conf import settings
from django.db.models import Avg

from apps.users.models import PilotProfile, UserAccount, CreditReview
from apps.common.order_numbers import generate_order_no
from .models import WorkOrder, OrderMatchLog, haversine_km


LICENSE_RANK = {
    'AOPA': 1,
    'CAAC-超视距': 3,
    'CAAC-视距内': 2,
    'CAAC': 2,
    'UTC': 2,
}


def _license_ok(req: str, pilot_level: str) -> bool:
    if not req:
        return True
    return req.lower() in (pilot_level or '').lower() or (pilot_level or '') in req


def match_score(order: WorkOrder, pilot: PilotProfile, distance_km: float) -> float:
    """综合：距离、执照、历史评价、在线空闲。"""
    distance_score = max(0, 100 - distance_km * 2)
    license_score = 100 if _license_ok(order.license_req, pilot.license_level) else 20
    avg = CreditReview.objects.filter(to_user=pilot.user, biz_type='order').aggregate(a=Avg('score'))['a']
    review_score = (float(avg) if avg else 3.5) * 20
    status_map = {'idle': 100, 'busy': 30, 'offline': 0}
    online_score = status_map.get(pilot.online_status, 0)
    return round(distance_score * 0.35 + license_score * 0.25 + review_score * 0.2 + online_score * 0.2, 2)


def smart_match_and_push(order: WorkOrder, limit: int = 20):
    pilots = PilotProfile.objects.select_related('user').filter(
        online_status__in=[PilotProfile.OnlineStatus.IDLE, PilotProfile.OnlineStatus.BUSY],
        verified=True,
    )
    # 未认证也允许演示匹配
    if not pilots.exists():
        pilots = PilotProfile.objects.select_related('user').filter(
            online_status__in=[PilotProfile.OnlineStatus.IDLE, PilotProfile.OnlineStatus.BUSY, PilotProfile.OnlineStatus.OFFLINE],
        )

    results = []
    for p in pilots:
        dist = haversine_km(order.lat, order.lng, p.lat, p.lng)
        if dist > order.match_radius_km and order.lat and p.lat:
            continue
        if not _license_ok(order.license_req, p.license_level) and order.license_req:
            # 硬性资质不满足：仍可记录低分但不优先
            pass
        score = match_score(order, p, dist)
        log, _ = OrderMatchLog.objects.update_or_create(
            order=order, pilot=p.user,
            defaults={'distance_km': dist, 'score': score},
        )
        results.append(log)

    results.sort(key=lambda x: x.score, reverse=True)
    order.status = WorkOrder.Status.MATCHED
    order.escrow_amount = order.budget
    order.platform_fee_rate = Decimal(str(settings.PLATFORM_FEE_RATE))
    order.save(update_fields=['status', 'escrow_amount', 'platform_fee_rate', 'updated_at'])
    return results[:limit]


def gen_order_no(prefix='WO'):
    return generate_order_no(prefix)
