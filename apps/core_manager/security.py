import hashlib
import ipaddress

from django.conf import settings
from django.core.cache import cache


def client_ip(request):
    value = request.META.get("REMOTE_ADDR", "")
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            value = forwarded.split(",", 1)[0].strip()

    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def private_cache_key(namespace, value):
    digest = hashlib.sha256(str(value or "unknown").encode("utf-8")).hexdigest()
    return f"core-security:{namespace}:{digest}"


def is_rate_limited(key, limit, timeout):
    """Atomically increment a fixed-window counter where the cache supports it."""
    limit = max(1, int(limit))
    timeout = max(1, int(timeout))
    if cache.add(key, 1, timeout):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        # The key expired between add() and incr(); start a fresh window.
        cache.set(key, 1, timeout)
        return False
    return count > limit
