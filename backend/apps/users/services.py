import logging

from django.db import transaction
from django.db.models import Avg

from .models import CreditReview
from rest_framework.exceptions import ValidationError


logger = logging.getLogger('flylink.users')


@transaction.atomic
def create_credit_review(*, from_user, validated_data):
    if validated_data.get('biz_type') == CreditReview.BizType.ORDER:
        from apps.orders.models import WorkOrder
        try:
            order = WorkOrder.objects.get(pk=validated_data.get('biz_id'), status=WorkOrder.Status.SETTLED)
        except WorkOrder.DoesNotExist:
            raise ValidationError('仅已结算订单的双方可以互评。')
        party_ids = {order.enterprise_id, order.pilot_id}
        if from_user.id not in party_ids or validated_data.get('to_user').id not in party_ids:
            raise ValidationError('只能评价该订单的另一方。')
    review = CreditReview.objects.create(from_user=from_user, **validated_data)
    average = (
        CreditReview.objects.filter(to_user=review.to_user)
        .aggregate(value=Avg('score'))['value']
        or 3
    )
    review.to_user.credit_score = min(1000, max(300, int(500 + float(average) * 100)))
    review.to_user.save(update_fields=['credit_score'])
    logger.info(
        'credit_review_created',
        extra={'user_id': from_user.pk, 'reviewed_user_id': review.to_user_id},
    )
    return review
