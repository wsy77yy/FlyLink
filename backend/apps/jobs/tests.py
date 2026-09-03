from django.urls import reverse
from rest_framework.test import APITestCase

from apps.jobs.models import JobPost
from apps.users.models import UserAccount


class JobCloseActionTests(APITestCase):
    def setUp(self):
        self.enterprise = UserAccount.objects.create_user(
            username='enterprise_close_test',
            password='Pass1234!',
            role=UserAccount.Role.ENTERPRISE,
        )
        self.job = JobPost.objects.create(
            enterprise=self.enterprise,
            title='电力巡检飞手',
            location='上海',
            salary_min=10000,
            salary_max=18000,
            license_req='CAAC-超视距',
            responsibilities='负责日常巡检',
            status=JobPost.Status.OPEN,
        )

    def test_enterprise_can_close_own_job(self):
        self.client.force_authenticate(user=self.enterprise)
        url = reverse('job-posts-close', kwargs={'pk': self.job.pk})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobPost.Status.CLOSED)
