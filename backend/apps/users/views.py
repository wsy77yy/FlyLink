from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.common.permissions import is_admin_user

from .models import UserAccount, EnterpriseProfile, PilotProfile, PilotResume, CreditReview
from .serializers import (
    UserSerializer, RegisterSerializer, EnterpriseProfileSerializer,
    PilotProfileSerializer, PilotResumeSerializer, CreditReviewSerializer,
)


from .selectors import (
    visible_credit_reviews,
    visible_pilot_profiles,
    visible_pilot_resumes,
)
from .services import create_credit_review


@extend_schema(
    request=RegisterSerializer,
    responses=inline_serializer(
        name='RegisterResponse',
        fields={
            'user': UserSerializer(),
            'access': serializers.CharField(),
            'refresh': serializers.CharField(),
        },
    ),
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


@extend_schema(responses=UserSerializer)
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
        return visible_pilot_profiles(user=self.request.user, action=self.action)

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
        serializer = self.get_serializer(
            profile,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PilotResumeViewSet(viewsets.ModelViewSet):
    queryset = PilotResume.objects.select_related('pilot__user').all()
    serializer_class = PilotResumeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return visible_pilot_resumes(
            user=self.request.user,
            action=self.action,
            mine=self.request.query_params.get('mine') == '1',
        )

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
        pilot = serializer.instance.pilot

        # 简历页里允许同步更新飞手基础展示字段，但只能通过上面的 queryset 改自己的简历。
        profile_data = {
            field: self.request.data[field]
            for field in ('license_level', 'years_exp', 'skills', 'real_name')
            if field in self.request.data
        }
        if profile_data:
            profile_serializer = PilotProfileSerializer(
                pilot,
                data=profile_data,
                partial=True,
                context={'request': self.request},
            )
            profile_serializer.is_valid(raise_exception=True)

        serializer.save()
        if profile_data:
            profile_serializer.save()

    def destroy(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response({'detail': '仅管理员可删除飞手简历'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class CreditReviewViewSet(viewsets.ModelViewSet):
    queryset = CreditReview.objects.select_related('from_user', 'to_user').all()
    serializer_class = CreditReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return visible_credit_reviews(user=self.request.user)

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

        serializer.instance = create_credit_review(
            from_user=self.request.user,
            validated_data=serializer.validated_data,
        )
