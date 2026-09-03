from rest_framework import serializers
from apps.users.models import UserAccount

from .models import (
    JobPost,
    JobApplication,
    ChatMessage,
    LaborContract,
    AgencyFee,
)


class JobPostSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    job_type_display = serializers.CharField(
        source='get_job_type_display',
        read_only=True,
    )

    class Meta:
        model = JobPost
        fields = '__all__'
        read_only_fields = [
            'enterprise',
            'created_at',
        ]

    def get_company_name(self, obj):
        if hasattr(obj.enterprise, 'enterprise_profile'):
            return obj.enterprise.enterprise_profile.company_name
        return obj.enterprise.username

    def validate(self, attrs):
        """
        岗位状态只能：
            OPEN -> CLOSED

        CLOSED 之后不能重新打开。
        """

        if self.instance:
            old_status = self.instance.status
            new_status = attrs.get('status', old_status)

            if old_status == JobPost.Status.CLOSED:
                if new_status != JobPost.Status.CLOSED:
                    raise serializers.ValidationError(
                        {'status': '已关闭的岗位不能重新开启。'}
                    )

            if (
                old_status == JobPost.Status.OPEN
                and new_status not in (
                    JobPost.Status.OPEN,
                    JobPost.Status.CLOSED,
                )
            ):
                raise serializers.ValidationError(
                    {'status': '无效的岗位状态。'}
                )

        return attrs


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(
        source='sender.username',
        read_only=True,
    )

    class Meta:
        model = ChatMessage
        fields = '__all__'
        read_only_fields = [
            'sender',
            'application',
            'created_at',
        ]


class LaborContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaborContract
        fields = '__all__'
        read_only_fields = [
            'application',
            'created_at',
            'signed_enterprise',
            'signed_pilot',
            'onboarded_at',
        ]


class AgencyFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgencyFee
        fields = '__all__'
        read_only_fields = [
            'application',
            'fee_rate',
            'amount',
            'status',
            'paid_at',
        ]


class JobApplicationSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(
        source='job.title',
        read_only=True,
    )
    pilot_name = serializers.CharField(
        source='pilot.username',
        read_only=True,
    )
    messages = ChatMessageSerializer(
        many=True,
        read_only=True,
    )
    contract = LaborContractSerializer(
        read_only=True,
    )
    agency_fee = AgencyFeeSerializer(
        read_only=True,
    )

    class Meta:
        model = JobApplication
        fields = '__all__'

        # 申请一旦创建，以下字段全部不能由前端直接修改
        read_only_fields = [
            'pilot',
            'match_score',
            'status',
            'source',
            'created_at',
        ]

    def validate_job(self, job):
        """
        主动投递时，岗位必须处于招聘中。
        """

        if self.instance is None:
            if job.status != JobPost.Status.OPEN:
                raise serializers.ValidationError(
                    '该岗位已经关闭，无法继续投递。'
                )

        return job


    def validate(self, attrs):
        """
        检查当前飞手是否已经存在该岗位申请。

        注意：
        RECOMMENDED 是合法的“待转为主动申请”状态，
        因此这里不能简单地把所有重复记录都拒绝。
        """

        if self.instance is not None:
            return attrs

        request = self.context.get('request')
        job = attrs.get('job')

        if not request or not request.user.is_authenticated:
            return attrs

        user = request.user

        if user.role != UserAccount.Role.PILOT:
            return attrs

        existing = JobApplication.objects.filter(
            job=job,
            pilot=user,
        ).first()

        if existing is not None:
            if existing.status == JobApplication.Status.RECOMMENDED:
                # 允许 views.perform_create()
                # 将 RECOMMENDED -> APPLIED
                return attrs

        raise serializers.ValidationError(
            {
                'job': (
                    '你已经存在该岗位的申请记录，'
                    '不能重复投递。'
                )
            }
        )

        return attrs