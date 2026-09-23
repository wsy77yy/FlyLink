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
