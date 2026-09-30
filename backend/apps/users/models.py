from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models

from apps.common.validators import credit_score_validators, review_score_validators


class UserAccount(AbstractUser):
    class Role(models.TextChoices):
        ENTERPRISE = 'enterprise', '需求企业方'
        PILOT = 'pilot', '个人飞手'
        ADMIN = 'admin', '平台管理员'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PILOT)
    phone = models.CharField(max_length=20, blank=True, default='')
    avatar = models.URLField(blank=True, default='')
    credit_score = models.IntegerField(default=600, validators=credit_score_validators)

    class Meta:
        db_table = 'user_account'
        verbose_name = '用户账号'
        constraints = [
            models.CheckConstraint(
                check=models.Q(credit_score__gte=300, credit_score__lte=1000),
                name='user_credit_score_300_1000',
            ),
        ]


class EnterpriseProfile(models.Model):
    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE, related_name='enterprise_profile')
    company_name = models.CharField(max_length=128)
    license_no = models.CharField(max_length=64, blank=True, default='')
    contact_name = models.CharField(max_length=64, blank=True, default='')
    address = models.CharField(max_length=255, blank=True, default='')
    verified = models.BooleanField(default=False)

    class Meta:
        db_table = 'enterprise_profile'


class PilotProfile(models.Model):
    class OnlineStatus(models.TextChoices):
        IDLE = 'idle', '空闲'
        BUSY = 'busy', '作业中'
        OFFLINE = 'offline', '离线'

    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE, related_name='pilot_profile')
    real_name = models.CharField(max_length=64, blank=True, default='')
    license_level = models.CharField(max_length=32, blank=True, default='')
    years_exp = models.IntegerField(default=0)
    online_status = models.CharField(max_length=20, choices=OnlineStatus.choices, default=OnlineStatus.OFFLINE)
    lat = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    skills = models.JSONField(default=list, blank=True)
    verified = models.BooleanField(default=False)

    class Meta:
        db_table = 'pilot_profile'
        constraints = [
            models.CheckConstraint(
                check=models.Q(years_exp__gte=0),
                name='pilot_years_exp_nonnegative',
            ),
            models.CheckConstraint(
                check=models.Q(lat__isnull=True) | models.Q(lat__gte=-90, lat__lte=90),
                name='pilot_lat_range',
            ),
            models.CheckConstraint(
                check=models.Q(lng__isnull=True) | models.Q(lng__gte=-180, lng__lte=180),
                name='pilot_lng_range',
            ),
        ]


class PilotResume(models.Model):
    pilot = models.OneToOneField(PilotProfile, on_delete=models.CASCADE, related_name='resume')
    summary = models.TextField(blank=True, default='')
    projects = models.JSONField(default=list, blank=True)
    portfolio = models.JSONField(default=list, blank=True)
    education = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pilot_resume'


class CreditReview(models.Model):
    class BizType(models.TextChoices):
        ORDER = 'order', '商单'
        JOB = 'job', '招聘'

    from_user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='reviews_given')
    to_user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='reviews_received')
    biz_type = models.CharField(max_length=20, choices=BizType.choices)
    biz_id = models.BigIntegerField(validators=[MinValueValidator(1)])
    score = models.IntegerField(validators=review_score_validators)
    tags = models.JSONField(default=list, blank=True)
    content = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'credit_review'
        unique_together = ('from_user', 'biz_type', 'biz_id')
        constraints = [
            models.CheckConstraint(
                check=models.Q(score__gte=1, score__lte=5),
                name='credit_review_score_1_5',
            ),
            models.CheckConstraint(
                check=~models.Q(from_user=models.F('to_user')),
                name='credit_review_users_differ',
            ),
            models.CheckConstraint(
                check=models.Q(biz_id__gt=0),
                name='credit_review_biz_id_positive',
            ),
        ]
