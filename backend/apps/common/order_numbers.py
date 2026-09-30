import re
import secrets

from django.utils import timezone


_PREFIX_RE = re.compile(r'^[A-Z][A-Z0-9]{1,5}$')


def generate_order_no(prefix: str) -> str:
    """Generate a sortable, collision-resistant order number of at most 32 chars."""
    normalized = (prefix or '').strip().upper()
    if not _PREFIX_RE.fullmatch(normalized):
        raise ValueError('订单号前缀必须是 2-6 位大写字母或数字，且以字母开头')

    date_part = timezone.localdate().strftime('%Y%m%d')
    random_length = 32 - len(normalized) - len(date_part)
    return f'{normalized}{date_part}{secrets.token_hex(12).upper()[:random_length]}'
