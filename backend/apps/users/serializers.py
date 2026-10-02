from decimal import Decimal

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework.validators import UniqueValidator
from .models import UserAccount, EnterpriseProfile, PilotProfile, PilotResume, CreditReview


USER_ROLE_CHOICES = list(UserAccount.Role.choices)
REGISTER_ROLE_CHOICES = [
    (UserAccount.Role.ENTERPRISE, '需求企业方'),
    (UserAccount.Role.PILOT, '个人飞手'),
]


class UserSerializer(serializers.ModelSerializer):
    """当前登录用户本人使用，允许返回手机号、邮箱等账户信息。"""

    class Meta:
        model = UserAccount
        fields = ['id', 'username', 'role', 'phone', 'email', 'avatar', 'credit_score', 'date_joined']
        read_only_fields = ['id', 'username', 'role', 'credit_score', 'date_joined']


class PublicUserSerializer(serializers.ModelSerializer):
    """公开展示使用，避免把手机号、邮箱暴露给其他用户。"""

    class Meta:
        model = UserAccount
        fields = ['id', 'username', 'role', 'avatar', 'credit_score']


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=64,
        validators=[UniqueValidator(queryset=UserAccount.objects.all(), message='该用户名已被使用。')],
    )
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=REGISTER_ROLE_CHOICES)
    phone = serializers.CharField(required=False, allow_blank=True)
    company_name = serializers.CharField(required=False, allow_blank=True)
    real_name = serializers.CharField(required=False, allow_blank=True)
    agreements_accepted = serializers.BooleanField(write_only=True)

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_agreements_accepted(self, value):
        if not value:
            raise serializers.ValidationError('请先阅读并同意用户协议、隐私政策和飞行安全承诺书。')
        return value

    def create(self, validated_data):
        validated_data.pop('agreements_accepted', None)
        role = validated_data['role']
        user = UserAccount.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            role=role,
            phone=validated_data.get('phone', ''),
            agreements_accepted_at=timezone.now(),
        )
        if role == UserAccount.Role.ENTERPRISE:
            EnterpriseProfile.objects.create(
                user=user,
                company_name=validated_data.get('company_name') or f'{user.username}企业',
            )
        else:
            pilot = PilotProfile.objects.create(
                user=user,
                real_name=validated_data.get('real_name') or user.username,
                online_status=PilotProfile.OnlineStatus.IDLE,
            )
            PilotResume.objects.create(pilot=pilot)
        return user


class EnterpriseProfileSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model = EnterpriseProfile
        fields = '__all__'
        read_only_fields = ['user', 'verified', 'review_status', 'review_reason', 'submitted_at', 'reviewed_at']


class PilotProfileSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    years_exp = serializers.IntegerField(min_value=0, max_value=80, required=False)
    lat = serializers.DecimalField(
        max_digits=10, decimal_places=6,
        min_value=Decimal('-90'), max_value=Decimal('90'),
        required=False, allow_null=True,
    )
    lng = serializers.DecimalField(
        max_digits=10, decimal_places=6,
        min_value=Decimal('-180'), max_value=Decimal('180'),
        required=False, allow_null=True,
    )

    class Meta:
        model = PilotProfile
        fields = '__all__'
        read_only_fields = ['user', 'verified', 'review_status', 'review_reason', 'submitted_at', 'reviewed_at', 'dispatch_suspended', 'suspension_reason', 'authorized_work_types']


class PilotResumeSerializer(serializers.ModelSerializer):
    pilot_id = serializers.IntegerField(source='pilot.id', read_only=True)
    real_name = serializers.CharField(source='pilot.real_name', read_only=True)
    license_level = serializers.CharField(source='pilot.license_level', read_only=True)
    years_exp = serializers.IntegerField(source='pilot.years_exp', read_only=True)
    skills = serializers.JSONField(source='pilot.skills', read_only=True)

    class Meta:
        model = PilotResume
        fields = [
            'id', 'pilot_id', 'real_name', 'license_level', 'years_exp', 'skills',
            'summary', 'projects', 'portfolio', 'education', 'updated_at',
        ]


class CreditReviewSerializer(serializers.ModelSerializer):
    from_username = serializers.CharField(source='from_user.username', read_only=True)
    to_username = serializers.CharField(source='to_user.username', read_only=True)

    class Meta:
        model = CreditReview
        fields = '__all__'
        read_only_fields = ['from_user']

    def validate(self, attrs):
        request = self.context.get('request')
        to_user = attrs.get('to_user', getattr(self.instance, 'to_user', None))
        if request and request.user.is_authenticated and to_user == request.user:
            raise serializers.ValidationError({'to_user': '不能评价自己。'})
        return attrs
