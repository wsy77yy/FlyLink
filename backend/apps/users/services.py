import logging

from django.db import transaction
from django.db.models import Avg

from .models import CreditReview


logger = logging.getLogger('flylink.users')


@transaction.atomic
def create_credit_review(*, from_user, validated_data):
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
