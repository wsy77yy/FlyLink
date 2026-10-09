from django.urls import path, re_path
from django.http import JsonResponse
from . import views as v
from django.conf import settings
import hashlib
def health(request): return JsonResponse({'application':'flylink-enterprise','version':'2.1','build':'desktop-20261002-r4','instance':hashlib.sha256(str(settings.BASE_DIR).encode()).hexdigest()[:16]})
urlpatterns=[path('api/health',health),path('api/demo-access',v.demo_access),path('api/session',v.public),path('api/auth',v.auth),path('api/state',v.state),path('api/profile',v.profile),path('api/users/<int:pk>/review',v.review_user),path('api/users/<int:pk>/files',v.profile_files),path('api/records',v.create),path('api/records/<int:pk>',v.detail),path('api/records/<int:pk>/action',v.action),path('api/upload',v.upload),path('api/files/<int:pk>',v.download),path('api/notices',v.notices),path('api/config',v.config),path('api/export',v.export),path('api/records/<int:pk>/export',v.export),re_path(r'^(?P<path>.*)$',v.page)]
