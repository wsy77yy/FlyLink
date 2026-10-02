from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.models import AuditLog, Notification
from apps.users.models import EnterpriseProfile, PilotProfile, UserAccount
from apps.orders.models import InvoiceRequest, Settlement, WithdrawalRequest, WorkOrder


class DocumentWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.enterprise = UserAccount.objects.create_user(username='enterprise-doc', password='x', role='enterprise')
        EnterpriseProfile.objects.create(user=self.enterprise, company_name='模拟企业', verified=True, review_status='approved')
        self.pilot = UserAccount.objects.create_user(username='pilot-doc', password='x', role='pilot')
        PilotProfile.objects.create(user=self.pilot, real_name='模拟飞手', verified=True, license_level='CAAC', online_status='idle')
        self.admin = UserAccount.objects.create_user(username='admin-doc', password='x', role='admin', is_staff=True)

    def order_payload(self):
        return {
            'work_type': 'inspect', 'location': '上海某机场周边',
            'execute_time': (timezone.now() + timedelta(days=3)).isoformat(),
            'area_or_duration': '2小时', 'budget': '1000.00',
            'license_req': 'CAAC', 'urgent': False,
        }

    def test_publish_requires_review_and_generates_risk(self):
        self.client.force_authenticate(self.enterprise)
        created = self.client.post('/api/orders/', self.order_payload(), format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['status'], 'pending_review')
        self.assertEqual(created.data['risk_level'], 'high')
        self.client.force_authenticate(self.admin)
        reviewed = self.client.post(f"/api/orders/{created.data['id']}/publish-review/", {'approved': True}, format='json')
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.data['status'], 'matched')
        self.assertTrue(AuditLog.objects.filter(action='order_publish_review').exists())

    def test_acceptance_rectification_and_dispute_resolution(self):
        order = WorkOrder.objects.create(order_no='WO-DOC-ACCEPT', enterprise=self.enterprise, pilot=self.pilot, work_type='inspect', location='测试点', execute_time=timezone.now() + timedelta(days=1), area_or_duration='1小时', budget=Decimal('1000'), status='reviewed', deposit_paid_at=timezone.now())
        self.client.force_authenticate(self.enterprise)
        response = self.client.post(f'/api/orders/{order.id}/acceptance/', {'result': 'rectify', 'checklist': ['track'], 'note': '轨迹缺少一段'}, format='json')
        self.assertEqual(response.data['status'], 'rectifying')
        order.status = WorkOrder.Status.DISPUTED
        order.save(update_fields=['status'])
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/api/orders/{order.id}/resolve-dispute/', {'result': 'refund', 'note': '模拟退款'}, format='json')
        self.assertEqual(response.data['status'], 'refunded')
        self.assertEqual(Settlement.objects.get(order=order).status, 'refunded')

    def test_persistent_notifications_and_finance_requests(self):
        self.client.force_authenticate(self.pilot)
        withdrawal = self.client.post('/api/common/finance-center/', {'amount': '100.00', 'account_hint': '尾号8888'}, format='json')
        self.assertEqual(withdrawal.status_code, 200)
        self.assertEqual(WithdrawalRequest.objects.count(), 1)
        notes = self.client.get('/api/common/notifications/')
        self.assertTrue(any(item['type'] == 'finance' for item in notes.data))
        self.client.post('/api/common/notifications/', {}, format='json')
        self.assertFalse(Notification.objects.filter(user=self.pilot, read_at__isnull=True).exists())

    def test_enterprise_invoice_request(self):
        self.client.force_authenticate(self.enterprise)
        response = self.client.post('/api/common/finance-center/', {'amount': '500.00', 'title': '模拟企业'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(InvoiceRequest.objects.get().status, 'pending')
