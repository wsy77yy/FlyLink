from .models import AuditLog, Notification


def notify(user, event_key, title, content='', link='', category='system'):
    if not user:
        return None
    item, _ = Notification.objects.update_or_create(
        user=user, event_key=event_key,
        defaults={'title': title, 'content': content, 'link': link, 'category': category},
    )
    return item


def audit(actor, action, target, detail=None):
    return AuditLog.objects.create(
        actor=actor, action=action, target_type=target.__class__.__name__,
        target_id=str(getattr(target, 'pk', '')), detail=detail or {},
    )
