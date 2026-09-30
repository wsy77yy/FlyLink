from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.users.models import CreditReview, PilotProfile, UserAccount

from .models import WorkOrder
from .services import smart_match_and_push


class MatchingQueryTests(TestCase):
    def setUp(self):
        self.enterprise = UserAccount.objects.create_user(
            username='matching-enterprise',
            role=UserAccount.Role.ENTERPRISE,
        )

    def create_pilots(self, count, offset=0):
        for index in range(offset, offset + count):
            user = UserAccount.objects.create_user(
                username=f'matching-pilot-{index}',
                role=UserAccount.Role.PILOT,
            )
            PilotProfile.objects.create(
                user=user,
                verified=True,
                online_status=PilotProfile.OnlineStatus.IDLE,
                lat=Decimal('31.230400'),
                lng=Decimal('121.473700'),
            )
            CreditReview.objects.create(
                from_user=self.enterprise,
                to_user=user,
                biz_type=CreditReview.BizType.ORDER,
                biz_id=index + 1,
                score=5,
            )

    def make_order(self, suffix):
        return WorkOrder.objects.create(
            order_no=f'WO-QUERY-{suffix}',
            enterprise=self.enterprise,
            work_type=WorkOrder.WorkType.AERIAL,
            location='上海',
            lat=Decimal('31.230400'),
            lng=Decimal('121.473700'),
            execute_time=timezone.now(),
            area_or_duration='1小时',
            budget=Decimal('1000.00'),
        )

    def test_matching_queries_do_not_grow_with_pilot_count(self):
        self.create_pilots(2)
        with CaptureQueriesContext(connection) as small:
            smart_match_and_push(self.make_order('SMALL'))

        self.create_pilots(18, offset=2)
        with CaptureQueriesContext(connection) as large:
            smart_match_and_push(self.make_order('LARGE'))

        self.assertLessEqual(len(large), len(small) + 1)
        self.assertEqual(len(large.captured_queries), len(large))
