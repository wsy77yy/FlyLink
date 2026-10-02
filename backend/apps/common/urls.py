from django.urls import path
from .views import admin_stats, platform_stats, notifications, admin_workspace, admin_verify_user, finance_center, enterprise_certification, admin_finance_review, admin_pilot_policy, admin_risk_config

urlpatterns = [
    path('stats/', platform_stats),
    path('admin-stats/', admin_stats),
    path('notifications/', notifications),
    path('admin-workspace/', admin_workspace),
    path('admin-users/<int:user_id>/verify/', admin_verify_user),
    path('enterprise-certification/', enterprise_certification),
    path('finance-center/', finance_center),
    path('admin-finance/<str:kind>/<int:item_id>/review/', admin_finance_review),
    path('admin-pilots/<int:user_id>/policy/', admin_pilot_policy),
    path('admin-risk-config/', admin_risk_config),
]
from .pilot_compliance import pilot_compliance_profile, pilot_document_upload

urlpatterns += [
    path("pilot-compliance/", pilot_compliance_profile, name="pilot-compliance-profile"),
    path("pilot-document-upload/", pilot_document_upload, name="pilot-document-upload"),
]
