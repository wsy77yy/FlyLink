from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.test import APITestCase

from apps.users.models import UserAccount, PilotProfile

from .models import WorkOrder
from .serializers import WorkOrderSerializer
from .services import gen_order_no


class EnterpriseOrderWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.enterprise = UserAccount.objects.create_user(
            username='enterprise-flow', role=UserAccount.Role.ENTERPRISE,
        )
        self.pilot = UserAccount.objects.create_user(
            username='pilot-flow', role=UserAccount.Role.PILOT,
        )
        PilotProfile.objects.create(
            user=self.pilot,
            real_name='测试飞手',
            license_level='CAAC-超视距',
            verified=True,
            insurance_expiry=(timezone.now() + timedelta(days=365)).date(),
            aircraft_registered=True,
            aircraft_registration_no='UAS-TEST-001',
        )
        self.admin = UserAccount.objects.create_user(
            username='admin-flow', role=UserAccount.Role.ADMIN, is_staff=True,
        )
        self.order = WorkOrder.objects.create(
            order_no='WO-FLOW-001',
            enterprise=self.enterprise,
            pilot=self.pilot,
            work_type=WorkOrder.WorkType.AERIAL,
            location='测试任务点',
            lat=Decimal('31.230400'),
            lng=Decimal('121.473700'),
            execute_time=timezone.now() + timedelta(days=1),
            area_or_duration='2小时',
            budget=Decimal('10000.00'),
            status=WorkOrder.Status.ACCEPTED,
            airspace_approved=True,
            weather_safe=True,
            compliance_reviewed_at=timezone.now(),
            weather_checked_at=timezone.now(),
        )

    def post_as(self, user, action, data=None):
        self.client.force_authenticate(user)
        return self.client.post(
            f'/api/orders/{self.order.pk}/{action}/',
            data or {},
            format='json',
        )

    def test_full_deposit_arrival_review_and_balance_workflow(self):
        response = self.post_as(self.enterprise, 'pay_deposit')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data['deposit_amount']), Decimal('2000.00'))

        self.assertEqual(self.post_as(self.pilot, 'declare').status_code, 200)
        response = self.post_as(self.pilot, 'arrive', {
            'lat': '31.230400', 'lng': '121.473700',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], WorkOrder.Status.ARRIVED)

        self.assertEqual(self.post_as(self.pilot, 'start_work').status_code, 200)
        self.assertEqual(self.post_as(self.pilot, 'finish_work').status_code, 200)
        self.assertEqual(self.post_as(self.pilot, 'submit_work').status_code, 200)
        self.assertEqual(self.post_as(self.admin, 'admin_review').status_code, 200)
        self.assertEqual(self.post_as(self.enterprise, 'pay_balance').status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, WorkOrder.Status.SETTLED)
        self.assertEqual(self.order.escrow_amount, Decimal('10000.00'))
        self.assertIsNotNone(self.order.balance_paid_at)

    def test_arrival_must_be_within_500_metres(self):
        self.order.status = WorkOrder.Status.DECLARED
        self.order.save(update_fields=['status'])

        response = self.post_as(self.pilot, 'arrive', {
            'lat': '32.230400', 'lng': '122.473700',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('500米', response.data['detail'])

    def test_cancel_after_one_hour_and_acceptance_charges_five_percent(self):
        WorkOrder.objects.filter(pk=self.order.pk).update(
            created_at=timezone.now() - timedelta(hours=2),
        )

        response = self.post_as(
            self.enterprise, 'cancel_order', {'reason': '计划调整'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data['penalty_amount']), Decimal('500.00'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, WorkOrder.Status.CANCELLED)


class WorkOrderValidationTests(APITestCase):
    def setUp(self):
        self.enterprise = UserAccount.objects.create_user(
            username='enterprise-validation', role=UserAccount.Role.ENTERPRISE,
        )
        self.payload = {
            'work_type': WorkOrder.WorkType.AERIAL,
            'location': '上海测试点',
            'execute_time': timezone.now() + timedelta(days=1),
            'area_or_duration': '2小时',
            'budget': '1000.00',
        }

    def test_rejects_budget_below_minimum_and_past_execution(self):
        low_budget = WorkOrderSerializer(data={**self.payload, 'budget': '99.99'})
        self.assertFalse(low_budget.is_valid())
        self.assertIn('budget', low_budget.errors)

        past = WorkOrderSerializer(data={
            **self.payload,
            'execute_time': timezone.now() - timedelta(minutes=1),
        })
        self.assertFalse(past.is_valid())
        self.assertIn('execute_time', past.errors)

    def test_order_numbers_are_unique_and_bounded(self):
        numbers = {gen_order_no() for _ in range(1000)}
        self.assertEqual(len(numbers), 1000)
        self.assertTrue(all(number.startswith('WO') and len(number) <= 32 for number in numbers))

    def test_serializer_returns_matching_chinese_weekday(self):
        order = WorkOrder.objects.create(
            enterprise=self.enterprise,
            order_no=gen_order_no(),
            **self.payload,
        )
        data = WorkOrderSerializer(order).data
        expected = ('星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日')[
            timezone.localtime(order.execute_time).weekday()
        ]
        self.assertEqual(data['execute_weekday'], expected)
