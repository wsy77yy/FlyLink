from django.utils.dateparse import parse_date
from django.utils import timezone
from django.core.files.storage import default_storage
from pathlib import Path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import PilotProfile


def _first_attr(instance, names):
    for name in names:
        if hasattr(instance, name):
            return name
    return None


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def pilot_compliance_profile(request):
    if getattr(request.user, "role", "") != "pilot":
        return Response({"detail": "仅飞手账号可以维护合规资料。"}, status=403)

    profile, _ = PilotProfile.objects.get_or_create(user=request.user)
    mapping = {
        "real_name": (profile, ("real_name",)),
        "id_card": (profile, ("id_card_no",)),
        "phone": (request.user, ("phone", "mobile")),
        "license_no": (profile, ("license_no", "license_number", "pilot_license_no")),
        "insurance_expiry": (profile, ("insurance_expiry",)),
        "aircraft_registration_no": (profile, ("aircraft_registration_no",)),
        "id_card_front_url": (profile, ("id_card_front_url",)),
        "id_card_back_url": (profile, ("id_card_back_url",)),
        "license_document_url": (profile, ("license_document_url",)),
        "insurance_document_url": (profile, ("insurance_document_url",)),
        "aircraft_document_url": (profile, ("aircraft_document_url",)),
    }

    if request.method == "PATCH":
        changed = False
        user_changed = False
        for public_name, (instance, candidates) in mapping.items():
            if public_name not in request.data:
                continue
            attr = _first_attr(instance, candidates)
            if not attr:
                continue
            value = request.data.get(public_name)
            if public_name == "insurance_expiry" and value:
                value = parse_date(str(value))
                if value is None:
                    return Response({"detail": "保险有效期格式不正确。"}, status=400)
            setattr(instance, attr, value or "")
            changed = True
            user_changed = user_changed or instance is request.user

        registration = request.data.get("aircraft_registration_no", "").strip()
        if hasattr(profile, "aircraft_registered") and "aircraft_registration_no" in request.data:
            profile.aircraft_registered = bool(registration)
            changed = True

        # 合规资料发生变化后需要管理员重新核验。
        if changed and hasattr(profile, "verified"):
            profile.verified = False
            profile.review_status = PilotProfile.ReviewStatus.PENDING
            profile.review_reason = ''
            profile.submitted_at = timezone.now()
            profile.reviewed_at = None
        if user_changed:
            request.user.save()
        if changed:
            profile.save()

    values = {}
    for public_name, (instance, candidates) in mapping.items():
        attr = _first_attr(instance, candidates)
        value = getattr(instance, attr, "") if attr else ""
        values[public_name] = value.isoformat() if hasattr(value, "isoformat") else value
    values["verified"] = bool(getattr(profile, "verified", False))
    values["review_status"] = profile.review_status
    values["review_status_display"] = profile.get_review_status_display()
    values["review_reason"] = profile.review_reason
    values["missing"] = [
        label for key, label in (
            ("real_name", "真实姓名"), ("id_card", "身份证号"), ("phone", "联系电话"),
            ("license_no", "飞手执照编号"), ("insurance_expiry", "保险有效期"),
            ("aircraft_registration_no", "航空器实名登记编号"),
            ("id_card_front_url", "身份证正面材料"), ("id_card_back_url", "身份证反面材料"),
            ("license_document_url", "飞手执照材料"), ("insurance_document_url", "保险凭证"),
            ("aircraft_document_url", "航空器登记证明"),
        ) if not values.get(key)
    ]
    return Response(values)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pilot_document_upload(request):
    if getattr(request.user, "role", "") != "pilot":
        return Response({"detail": "仅飞手账号可以上传认证材料。"}, status=403)
    profile, _ = PilotProfile.objects.get_or_create(user=request.user)
    fields = {
        "id_card_front": "id_card_front_url", "id_card_back": "id_card_back_url",
        "license_document": "license_document_url", "insurance_document": "insurance_document_url",
        "aircraft_document": "aircraft_document_url",
    }
    saved = {}
    for upload_name, model_field in fields.items():
        upload = request.FILES.get(upload_name)
        if not upload:
            continue
        if upload.size > 8 * 1024 * 1024:
            return Response({"detail": f"{upload_name} 文件不能超过 8MB。"}, status=400)
        suffix = Path(upload.name).suffix.lower()
        if suffix not in {'.jpg', '.jpeg', '.png', '.webp', '.pdf'}:
            return Response({"detail": "认证材料仅支持 JPG、PNG、WEBP 或 PDF。"}, status=400)
        relative = default_storage.save(f"certifications/{request.user.id}/{upload_name}{suffix}", upload)
        url = default_storage.url(relative)
        setattr(profile, model_field, url)
        saved[model_field] = url
    if not saved:
        return Response({"detail": "请选择需要上传的认证材料。"}, status=400)
    profile.verified = False
    profile.review_status = PilotProfile.ReviewStatus.PENDING
    profile.review_reason = ''
    profile.submitted_at = timezone.now()
    profile.reviewed_at = None
    profile.save()
    return Response({"documents": saved, "review_status": profile.review_status})
