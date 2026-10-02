from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.users.models import UserAccount
from apps.common.validators import salary_validators


class JobPost(models.Model):
    class JobType(models.TextChoices):
        FULLTIME = 'fulltime', '全职'
        PARTTIME = 'parttime', '长期兼职'

    class Status(models.TextChoices):
        OPEN = 'open', '招聘中'
        CLOSED = 'closed', '已关闭'

    enterprise = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='job_posts')
    title = models.CharField(max_length=128)
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.FULLTIME)
    location = models.CharField(max_length=255)
    salary_min = models.IntegerField(validators=salary_validators)
    salary_max = models.IntegerField(validators=salary_validators)
    license_req = models.CharField(max_length=64, blank=True, default='')
    benefits = models.TextField(blank=True, default='')
    responsibilities = models.TextField(blank=True, default='')
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'job_post'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(salary_min__gte=3000, salary_min__lte=1000000),
                name='job_salary_min_range',
            ),
            models.CheckConstraint(
                check=models.Q(salary_max__gte=3000, salary_max__lte=1000000),
                name='job_salary_max_range',
            ),
            models.CheckConstraint(
                check=models.Q(salary_max__gte=models.F('salary_min')),
                name='job_salary_ordered',
            ),
        ]


class JobApplication(models.Model):
    class Status(models.TextChoices):
        RECOMMENDED = 'recommended', 'AI推荐'
        APPLIED = 'applied', '已投递'
        INTERVIEW = 'interview', '面试中'
        OFFERED = 'offered', '已发Offer'
        HIRED = 'hired', '已入职'
        REJECTED = 'rejected', '已拒绝'

    class Source(models.TextChoices):
        SELF = 'self', '主动投递'
        AI = 'ai', 'AI推荐'

    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name='applications')
    pilot = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='job_applications')
    match_score = models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPLIED)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.SELF)
    created_at = models.DateTimeField(auto_now_add=True)
    interview_at = models.DateTimeField(null=True, blank=True)
    interview_note = models.TextField(blank=True, default='')
    rejection_reason = models.TextField(blank=True, default='')
    status_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'job_application'
        unique_together = ('job', 'pilot')
        constraints = [
            models.CheckConstraint(
                check=models.Q(match_score__gte=0, match_score__lte=100),
                name='job_match_score_0_100',
            ),
        ]


class ChatMessage(models.Model):
    class MsgType(models.TextChoices):
        TEXT = 'text', '文本'
        INTERVIEW = 'interview_invite', '面试邀约'

    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    content = models.TextField()
    msg_type = models.CharField(max_length=20, choices=MsgType.choices, default=MsgType.TEXT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_message'
        ordering = ['created_at']


class LaborContract(models.Model):
    application = models.OneToOneField(JobApplication, on_delete=models.CASCADE, related_name='contract')
    contract_url = models.URLField(blank=True, default='')
    contract_content = models.TextField(blank=True, default='')
    signed_enterprise = models.BooleanField(default=False)
    signed_pilot = models.BooleanField(default=False)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'labor_contract'


class AgencyFee(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '待结算'
        PAID = 'paid', '已结算'

    application = models.OneToOneField(JobApplication, on_delete=models.CASCADE, related_name='agency_fee')
    fee_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.12)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'agency_fee'
        constraints = [
            models.CheckConstraint(
                check=models.Q(fee_rate__gte=0, fee_rate__lte=1),
                name='agency_fee_rate_0_1',
            ),
            models.CheckConstraint(
                check=models.Q(amount__gte=0),
                name='agency_fee_amount_nonnegative',
            ),
        ]
