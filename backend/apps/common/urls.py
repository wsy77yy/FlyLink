from django.urls import path
from .views import admin_stats, platform_stats

urlpatterns = [
    path('stats/', platform_stats),
    path('admin-stats/', admin_stats),
]
