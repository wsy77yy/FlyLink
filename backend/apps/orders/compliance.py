from datetime import timedelta
from django.utils import timezone


def evaluate_compliance(order, pilot):
    profile = getattr(pilot, 'pilot_profile', None)
    if profile and profile.license_expiry and profile.license_expiry < timezone.localdate() and not profile.dispatch_suspended:
        profile.dispatch_suspended = True
        profile.suspension_reason = '飞手执照已过有效期，系统自动暂停派单。'
        profile.save(update_fields=['dispatch_suspended', 'suspension_reason'])
    required = (order.license_req or '').strip().lower()
    actual = (getattr(profile, 'license_level', '') or '').strip().lower()
    license_date_ok = bool(profile and (not profile.license_expiry or profile.license_expiry >= timezone.localdate()))
    scope_ok = bool(profile and (not profile.authorized_work_types or order.work_type in profile.authorized_work_types))
    active_ok = bool(profile and not profile.dispatch_suspended)
    license_ok = bool(profile and profile.verified and actual and license_date_ok and scope_ok and active_ok and (not required or required in actual or actual in required))
    insurance_ok = bool(profile and profile.insurance_expiry and profile.insurance_expiry >= timezone.localdate())
    aircraft_ok = bool(profile and profile.aircraft_registered and profile.aircraft_registration_no)
    now = timezone.now()
    airspace_ok = bool(order.airspace_approved and (not order.airspace_valid_until or order.airspace_valid_until >= now))
    weather_checked_at = order.weather_checked_at or order.compliance_reviewed_at
    weather_ok = bool(order.weather_safe and weather_checked_at and weather_checked_at >= now - timedelta(hours=6))
    gates = [
        {'key': 'license', 'label': '证照与作业范围有效', 'passed': license_ok, 'detail': (profile.suspension_reason if profile and profile.dispatch_suspended else (actual or '未登记执照'))},
        {'key': 'insurance', 'label': '保险适用', 'passed': insurance_ok, 'detail': str(profile.insurance_expiry) if profile and profile.insurance_expiry else '未登记保险'},
        {'key': 'aircraft', 'label': '航空器已登记', 'passed': aircraft_ok, 'detail': getattr(profile, 'aircraft_registration_no', '') or '未登记航空器'},
        {'key': 'airspace', 'label': '空域条件满足', 'passed': airspace_ok, 'detail': ('有效至 ' + timezone.localtime(order.airspace_valid_until).strftime('%Y-%m-%d %H:%M')) if airspace_ok and order.airspace_valid_until else ('管理员已复核' if airspace_ok else '待复核或批复已过期')},
        {'key': 'weather', 'label': '天气不超限', 'passed': weather_ok, 'detail': ('最近 6 小时内已复核' if weather_ok else '天气复核已过期或未通过')},
    ]
    return {'passed': all(item['passed'] for item in gates), 'gates': gates}
