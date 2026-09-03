from django.db.models import Avg, Q
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserAccount, EnterpriseProfile, PilotProfile, PilotResume, CreditReview
from .serializers import (
    UserSerializer, RegisterSerializer, EnterpriseProfileSerializer,
    PilotProfileSerializer, PilotResumeSerializer, CreditReviewSerializer,
)


def is_admin_user(user):
    return (
        user
        and user.is_authenticated
        and (user.role == UserAccount.Role.ADMIN or user.is_staff)
    )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    refresh = RefreshToken.for_user(user)
    return Response({
        'user': UserSerializer(user).data,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    data = UserSerializer(request.user).data
    if request.user.role == UserAccount.Role.ENTERPRISE and hasattr(request.user, 'enterprise_profile'):
        data['profile'] = EnterpriseProfileSerializer(request.user.enterprise_profile).data
    if request.user.role == UserAccount.Role.PILOT and hasattr(request.user, 'pilot_profile'):
        data['profile'] = PilotProfileSerializer(request.user.pilot_profile).data
        if hasattr(request.user.pilot_profile, 'resume'):
            data['resume'] = PilotResumeSerializer(request.user.pilot_profile.resume).data
    return Response(data)


class PilotProfileViewSet(viewsets.ModelViewSet):
    queryset = PilotProfile.objects.select_related('user').all()
    serializer_class = PilotProfileSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # 修改资料时，飞手只能改自己；管理员可以管理全部。
        if self.action in ('update', 'partial_update', 'destroy'):
            if not user.is_authenticated:
                return qs.none()
            if is_admin_user(user):
                return qs
            if user.role == UserAccount.Role.PILOT:
                return qs.filter(user=user)
            return qs.none()

        return qs

    def create(self, request, *args, **kwargs):
        # 资料通常在注册时自动创建，普通用户不应手动创建他人资料。
        if not is_admin_user(request.user):
            return Response({'detail': '仅管理员可创建飞手资料'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response({'detail': '仅管理员可删除飞手资料'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['patch'], url_path='me/location')
    def update_my_location(self, request):
        if request.user.role != UserAccount.Role.PILOT:
            return Response({'detail': '仅飞手可更新位置'}, status=status.HTTP_403_FORBIDDEN)

        if not hasattr(request.user, 'pilot_profile'):
            return Response({'detail': '飞手资料不存在'}, status=status.HTTP_404_NOT_FOUND)

        profile = request.user.pilot_profile
        profile.lat = request.data.get('lat', profile.lat)
        profile.lng = request.data.get('lng', profile.lng)
        profile.online_status = request.data.get('online_status', profile.online_status)
        profile.save()
        return Response(PilotProfileSerializer(profile).data)


class PilotResumeViewSet(viewsets.ModelViewSet):
    queryset = PilotResume.objects.select_related('pilot__user').all()
    serializer_class = PilotResumeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # 修改简历时，飞手只能改自己的简历；管理员可以管理全部。
        if self.action in ('update', 'partial_update', 'destroy'):
            if not user.is_authenticated:
                return qs.none()
            if is_admin_user(user):
                return qs
            if user.role == UserAccount.Role.PILOT and hasattr(user, 'pilot_profile'):
                return qs.filter(pilot=user.pilot_profile)
            return qs.none()

        if self.request.query_params.get('mine') == '1':
            if not user.is_authenticated:
                return qs.none()
            if is_admin_user(user):
                return qs
            if user.role == UserAccount.Role.PILOT and hasattr(user, 'pilot_profile'):
                return qs.filter(pilot=user.pilot_profile)
            return qs.none()

        return qs

    def create(self, request, *args, **kwargs):
        if request.user.role != UserAccount.Role.PILOT:
            return Response({'detail': '仅飞手可创建简历'}, status=status.HTTP_403_FORBIDDEN)

        if not hasattr(request.user, 'pilot_profile'):
            return Response({'detail': '飞手资料不存在'}, status=status.HTTP_404_NOT_FOUND)

        profile = request.user.pilot_profile

        if hasattr(profile, 'resume'):
            return Response({'detail': '简历已存在'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(pilot=profile)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        serializer.save()
        pilot = serializer.instance.pilot

        # 简历页里允许同步更新飞手基础展示字段，但只能通过上面的 queryset 改自己的简历。
        for field in ('license_level', 'years_exp', 'skills', 'real_name'):
            if field in self.request.data:
                setattr(pilot, field, self.request.data[field])
        pilot.save()

    def destroy(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response({'detail': '仅管理员可删除飞手简历'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class CreditReviewViewSet(viewsets.ModelViewSet):
    queryset = CreditReview.objects.select_related('from_user', 'to_user').all()
    serializer_class = CreditReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            return qs.none()

        if is_admin_user(user):
            return qs

        # 普通用户只能看到自己发出的评价和收到的评价。
        return qs.filter(Q(from_user=user) | Q(to_user=user))

    def update(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response({'detail': '评价提交后不可由普通用户修改'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response({'detail': '评价提交后不可由普通用户修改'}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response({'detail': '仅管理员可删除评价'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        to_user = serializer.validated_data.get('to_user')
        score = serializer.validated_data.get('score')

        if to_user == self.request.user:
            raise PermissionDenied('不能评价自己')

        if score is None or score < 1 or score > 5:
            raise ValidationError({'score': '评分必须在 1 到 5 之间'})

        review = serializer.save(from_user=self.request.user)
        avg = CreditReview.objects.filter(to_user=review.to_user).aggregate(a=Avg('score'))['a'] or 3

        # 评价映射到信用画像：基础 500 + 均分*100
        review.to_user.credit_score = min(1000, max(300, int(500 + float(avg) * 100)))
        review.to_user.save(update_fields=['credit_score'])
