from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import UserAccount

from .models import DroneDevice, RentalOrder


class RentalRolePermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = UserAccount.objects.create_user(
            username='admin',
            password='test-pass',
            role=UserAccount.Role.ADMIN,
        )
        self.pilot = UserAccount.objects.create_user(
            username='pilot',
            password='test-pass',
            role=UserAccount.Role.PILOT,
        )
        self.other_pilot = UserAccount.objects.create_user(
            username='other-pilot',
            password='test-pass',
            role=UserAccount.Role.PILOT,
        )
        self.device = DroneDevice.objects.create(
            model_name='Test Drone',
            daily_price=100,
            monthly_price=2000,
            deposit=500,
            stock=2,
        )

    def test_admin_cannot_create_rental_order(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post('/api/rental/orders/', {})

        self.assertEqual(response.status_code, 403)

    def test_user_cannot_pay_another_users_rental_order(self):
        order = RentalOrder.objects.create(
            order_no='RL-OTHER-001',
            user=self.other_pilot,
            device=self.device,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            deposit_paid=500,
            insurance_fee=76,
            rent_amount=200,
        )
        self.client.force_authenticate(self.pilot)

        response = self.client.post(
            f'/api/rental/orders/{order.pk}/pay/',
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_calendar_date_and_past_date_are_rejected(self):
        self.client.force_authenticate(self.pilot)
        invalid = self.client.post('/api/rental/orders/', {
            'device': self.device.pk,
            'start_date': '2026-13-01',
            'end_date': '2026-13-02',
        }, format='json')
        self.assertEqual(invalid.status_code, 400)

        yesterday = date.today() - timedelta(days=1)
        past = self.client.post('/api/rental/orders/', {
            'device': self.device.pk,
            'start_date': yesterday.isoformat(),
            'end_date': date.today().isoformat(),
        }, format='json')
        self.assertEqual(past.status_code, 400)

    def test_rental_response_contains_calendar_weekdays(self):
        self.client.force_authenticate(self.pilot)
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=1)
        response = self.client.post('/api/rental/orders/', {
            'device': self.device.pk,
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, 201)
        weekdays = ('星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日')
        self.assertEqual(response.data['start_weekday'], weekdays[start.weekday()])
