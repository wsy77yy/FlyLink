import math
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.users.models import UserAccount


def haversine_km(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return 9999.0
    r = 6371.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlmb = math.radians(float(lng2) - float(lng1))
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class WorkOrder(models.Model):
    class WorkType(models.TextChoices):
        PLANT = 'plant', '植保'
        INSPECT = 'inspect', '巡检'
        AERIAL = 'aerial', '航拍'
        SURVEY = 'survey', '测绘'
        LOGISTICS = 'logistics', '物流配送'
        EMERGENCY = 'emergency', '应急救援'
        SECURITY = 'security', '安防监控'
        SHOW = 'show', '表演航展'
        TRAINING = 'training', '培训考试'
        OTHER = 'other', '其它自定义'

    class Status(models.TextChoices):
        PENDING = 'pending', '待匹配'
        MATCHED = 'matched', '已推送'
        ACCEPTED = 'accepted', '已接单'
        DECLARED = 'declared', '已申报'
        ARRIVED = 'arrived', '飞手已到达'
        WORKING = 'working', '作业中'
        FINISHED = 'finished', '作业已完成'
        SUBMITTED = 'submitted', '待验收'
        REVIEWED = 'reviewed', '管理员已审核'
        ACCEPTED_DONE = 'accepted_done', '已验收'
        SETTLED = 'settled', '已结算'
        CANCELLED = 'cancelled', '已取消'

    order_no = models.CharField(max_length=32, unique=True)
    enterprise = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='published_orders')
    pilot = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_orders')
    work_type = models.CharField(max_length=32, choices=WorkType.choices)
    custom_work_type = models.CharField(max_length=64, blank=True, default='', verbose_name='自定义作业类型')
    location = models.CharField(max_length=255)
    region_code = models.CharField(max_length=32, blank=True, default='', verbose_name='行政区划代码')
    province = models.CharField(max_length=64, blank=True, default='')
    city = models.CharField(max_length=64, blank=True, default='')
    district = models.CharField(max_length=64, blank=True, default='')
    lat = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    execute_time = models.DateTimeField()
    area_or_duration = models.CharField(max_length=64)
    budget = models.DecimalField(max_digits=12, decimal_places=2)
    license_req = models.CharField(max_length=64, blank=True, default='')
    urgent = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    match_radius_km = models.FloatField(default=50)
    assigned_by_admin = models.BooleanField(default=False)
    platform_fee_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0800'))
    escrow_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deposit_paid_at = models.DateTimeField(null=True, blank=True)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_paid_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    arrival_lat = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    arrival_lng = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    arrival_distance_km = models.FloatField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    submission_deadline = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    admin_reviewed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_penalty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cancel_reason = models.TextField(blank=True, default='')
    actual_area = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    remark = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def work_type_label(self):
        if self.work_type == self.WorkType.OTHER and self.custom_work_type:
            return self.custom_work_type
        return self.get_work_type_display()

    class Meta:
        db_table = 'work_order'
        ordering = ['-created_at']


class OrderMatchLog(models.Model):
    order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='match_logs')
    pilot = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='match_logs')
    distance_km = models.FloatField(default=0)
    score = models.FloatField(default=0)
    pushed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_match_log'


class FlightPlan(models.Model):
    class DeclareStatus(models.TextChoices):
        DRAFT = 'draft', '草稿'
        SUBMITTED = 'submitted', '已提交'
        APPROVED = 'approved', '已批复'

    order = models.OneToOneField(WorkOrder, on_delete=models.CASCADE, related_name='flight_plan')
    plan_content = models.JSONField(default=dict)
    declare_status = models.CharField(max_length=20, choices=DeclareStatus.choices, default=DeclareStatus.DRAFT)
    external_ref = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'flight_plan'


class WorkTrack(models.Model):
    order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='tracks')
    lat = models.DecimalField(max_digits=10, decimal_places=6)
    lng = models.DecimalField(max_digits=10, decimal_places=6)
    altitude = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'work_track'
        ordering = ['recorded_at']


class WorkMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = 'image', '图片'
        VIDEO = 'video', '视频'

    order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='medias')
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    url = models.URLField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'work_media'


class Settlement(models.Model):
    class Status(models.TextChoices):
        HOLDING = 'holding', '托管中'
        PAID = 'paid', '已打款'
        REFUNDED = 'refunded', '已退款'

    order = models.OneToOneField(WorkOrder, on_delete=models.CASCADE, related_name='settlement')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2)
    pilot_income = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.HOLDING)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'settlement'
