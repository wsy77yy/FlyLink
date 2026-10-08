from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.users.models import UserAccount
from apps.jobs.models import JobPost
from apps.orders.models import WorkOrder
from apps.rental.models import DroneModel, DroneUnit


class AdminStatsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = UserAccount.objects.create_user(
            username='platform-admin',
            password='test-pass',
            role=UserAccount.Role.ADMIN,
        )
        self.enterprise = UserAccount.objects.create_user(
            username='enterprise',
            password='test-pass',
            role=UserAccount.Role.ENTERPRISE,
        )
        UserAccount.objects.create_user(
            username='pilot',
            password='test-pass',
            role=UserAccount.Role.PILOT,
        )

    def test_admin_can_read_platform_management_stats(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/common/admin-stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user_count'], 2)
        self.assertEqual(response.data['enterprise_count'], 1)
        self.assertEqual(response.data['pilot_count'], 1)
        self.assertIn('device_total', response.data)
        self.assertIn('order_count', response.data)

    def test_enterprise_cannot_read_admin_stats(self):
        self.client.force_authenticate(self.enterprise)

        response = self.client.get('/api/common/admin-stats/')

        self.assertEqual(response.status_code, 403)

    def test_response_has_request_id(self):
        response = self.client.get('/api/common/stats/', HTTP_X_REQUEST_ID='trace-test-001')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Request-ID'], 'trace-test-001')

    def test_openapi_schema_and_swagger_are_available(self):
        schema = self.client.get('/api/schema/')
        docs = self.client.get('/api/docs/')

        self.assertEqual(schema.status_code, 200)
        self.assertEqual(docs.status_code, 200)
        self.assertIn('/api/orders/', schema.content.decode('utf-8'))

    @patch('apps.common.views.socket.socket')
    def test_demo_access_returns_lan_url_for_local_roadshow(self, socket_mock):
        client = MagicMock()
        client.getsockname.return_value = ('10.20.30.40', 54321)
        socket_mock.return_value.__enter__.return_value = client

        response = self.client.get(
            '/api/common/demo-access/',
            HTTP_HOST='127.0.0.1:8000',
            SERVER_PORT='8000',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_lan'])
        self.assertEqual(response.data['base_url'], 'http://10.20.30.40:8000/')


class SeedDemoTests(TestCase):
    def test_seed_demo_is_idempotent(self):
        call_command('seed_demo', verbosity=0)
        call_command('seed_demo', verbosity=0)

        self.assertEqual(UserAccount.objects.filter(username='admin').count(), 1)
        self.assertEqual(UserAccount.objects.filter(username='enterprise1').count(), 1)
        self.assertEqual(UserAccount.objects.filter(username='pilot1').count(), 1)
        self.assertEqual(WorkOrder.objects.filter(remark__startswith='seed_demo:').count(), 2)
        self.assertEqual(JobPost.objects.filter(title='资深植保飞手（全职）').count(), 1)
        self.assertEqual(DroneModel.objects.count(), 3)
        self.assertEqual(DroneUnit.objects.count(), 10)
