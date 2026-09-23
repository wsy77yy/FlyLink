from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponseNotFound
from django.urls import path, include, re_path
from django.conf.urls.static import static
from django.views.decorators.cache import never_cache
from django.views.static import serve as static_serve
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


@never_cache
def spa_index(_request, _path=None):
    """Vue history 模式：非 API 路由回退到 index.html。"""
    index = Path(settings.FRONTEND_DIST) / 'index.html'
    if not index.exists():
        return HttpResponseNotFound(
            '前端未构建。请先在 frontend 目录执行 npm run build，'
            '或使用开发模式：前端 npm run dev + 后端 runserver。'
        )
    return FileResponse(index.open('rb'), content_type='text/html; charset=utf-8')


urlpatterns = [
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/users/', include('apps.users.urls')),
    path('api/orders/', include('apps.orders.urls')),
    path('api/jobs/', include('apps.jobs.urls')),
    path('api/rental/', include('apps.rental.urls')),
    path('api/common/', include('apps.common.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# 托管打包后的前端静态资源
if Path(settings.FRONTEND_DIST).exists():
    urlpatterns += [
        re_path(
            r'^assets/(?P<path>.*)$',
            static_serve,
            {'document_root': str(Path(settings.FRONTEND_DIST) / 'assets')},
        ),
        re_path(
            r'^(?P<path>favicon\.svg)$',
            static_serve,
            {'document_root': str(settings.FRONTEND_DIST)},
        ),
        re_path(
            r'^(?P<path>admin-dashboard\.html)$',
            static_serve,
            {'document_root': str(settings.FRONTEND_DIST)},
        ),
        # SPA 回退（放最后，避免拦截 /api）
        re_path(r'^(?!api/).*$', spa_index),
    ]
