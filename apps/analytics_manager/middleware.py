import hashlib
import hmac
import ipaddress
import logging
import re
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core_manager.security import client_ip

from .models import (
    AnalyticsSettings,
    DailyPageStat,
    DailySiteStat,
    DailyUniqueVisitor,
    Visit,
)


logger = logging.getLogger(__name__)
BOT_PATTERN = re.compile(
    r"bot|crawler|spider|slurp|bingpreview|facebookexternalhit|"
    r"headless|lighthouse|pagespeed|uptimerobot|monitoring",
    re.IGNORECASE,
)
SENSITIVE_SUFFIXES = ("password", "passwd", "token", "secret", "api_key")
ALWAYS_EXCLUDED_PREFIXES = (
    "/admin/",
    "/static/",
    "/media/",
    "/rosetta/",
    "/ai-assistant/health/",
    "/favicon.ico",
    "/favicon.png",
    "/apple-touch-icon",
)


def _configuration():
    configuration = cache.get("analytics:configuration")
    if configuration is None:
        configuration = AnalyticsSettings.get_solo()
        cache.set("analytics:configuration", configuration, 60)
    return configuration


def _digest(value):
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _masked_ip(value):
    if not value:
        return None
    address = ipaddress.ip_address(value)
    prefix = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False).network_address)


def _safe_query_string(request, configuration):
    if not configuration.record_query_string or not request.META.get("QUERY_STRING"):
        return ""
    sensitive = configuration.sensitive_parameters()
    values = []
    for key, value in parse_qsl(request.META["QUERY_STRING"], keep_blank_values=True):
        normalized = key.casefold()
        if normalized in sensitive or normalized.endswith(SENSITIVE_SUFFIXES):
            value = "[redacted]"
        values.append((key[:255], value[:1000]))
    return urlencode(values, doseq=True)[:4000]


def _store_visit(request, response, configuration):
    address = client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
    ip_address = None
    ip_hash = ""
    visitor_hash = ""

    if address and configuration.ip_storage_mode != AnalyticsSettings.IPStorageMode.NONE:
        ip_hash = _digest(address)
        visitor_hash = _digest(f"{address}|{user_agent}")
        if configuration.ip_storage_mode == AnalyticsSettings.IPStorageMode.FULL:
            ip_address = address
        elif configuration.ip_storage_mode == AnalyticsSettings.IPStorageMode.MASKED:
            ip_address = _masked_ip(address)
    elif request.user.is_authenticated and request.user.pk:
        visitor_hash = _digest(f"user:{request.user.pk}")

    match = getattr(request, "resolver_match", None)
    view_name = (getattr(match, "view_name", "") or "")[:255]
    app_name = (getattr(match, "app_name", "") or "")[:100]
    path = request.path[:1000]
    today = timezone.localdate()

    with transaction.atomic():
        if configuration.collection_mode == AnalyticsSettings.CollectionMode.DETAILED:
            Visit.objects.create(
                path=path,
                query_string=_safe_query_string(request, configuration),
                method=request.method,
                status_code=response.status_code,
                view_name=view_name,
                app_name=app_name,
                user=(
                    request.user
                    if request.user.is_authenticated and request.user.pk
                    else None
                ),
                ip_address=ip_address,
                ip_hash=ip_hash,
                visitor_hash=visitor_hash,
                referrer=request.META.get("HTTP_REFERER", "")[:2000],
                user_agent=user_agent,
            )
        stat, created = DailyPageStat.objects.get_or_create(
            date=today,
            path=path,
            defaults={"view_name": view_name, "views": 1},
        )
        if not created:
            DailyPageStat.objects.filter(pk=stat.pk).update(
                views=F("views") + 1,
                view_name=view_name,
            )
        if visitor_hash:
            _visitor, is_new = DailyUniqueVisitor.objects.get_or_create(
                date=today,
                path=path,
                visitor_hash=visitor_hash,
            )
            if is_new:
                DailyPageStat.objects.filter(pk=stat.pk).update(
                    unique_visitors=F("unique_visitors") + 1
                )
        site_stat, site_created = DailySiteStat.objects.get_or_create(
            date=today,
            defaults={"views": 1},
        )
        if not site_created:
            DailySiteStat.objects.filter(pk=site_stat.pk).update(views=F("views") + 1)
        if visitor_hash:
            _site_visitor, is_new_site_visitor = DailyUniqueVisitor.objects.get_or_create(
                date=today,
                path="",
                visitor_hash=visitor_hash,
            )
            if is_new_site_visitor:
                DailySiteStat.objects.filter(pk=site_stat.pk).update(
                    unique_visitors=F("unique_visitors") + 1
                )


def _cleanup_expired_details(configuration):
    if not cache.add("analytics:retention-cleanup", True, 60 * 60 * 24):
        return
    cutoff = timezone.now() - timedelta(days=configuration.retention_days)
    Visit.objects.filter(created_at__lt=cutoff).delete()
    # These rows are only needed while counting today's returning visitors.
    # Keep yesterday as a timezone safety margin, then discard them.
    unique_cutoff = timezone.localdate() - timedelta(days=1)
    DailyUniqueVisitor.objects.filter(date__lt=unique_cutoff).delete()


class VisitTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if request.method != "GET" or any(
                request.path.startswith(prefix) for prefix in ALWAYS_EXCLUDED_PREFIXES
            ):
                return response
            if response.status_code < 200 or response.status_code >= 400:
                return response
            configuration = _configuration()
            if not configuration.enabled:
                return response
            if any(request.path.startswith(prefix) for prefix in configuration.excluded_prefixes()):
                return response
            if configuration.exclude_staff and request.user.is_authenticated and request.user.is_staff:
                return response
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            if configuration.exclude_bots and BOT_PATTERN.search(user_agent):
                return response
            _store_visit(request, response, configuration)
            _cleanup_expired_details(configuration)
        except Exception:
            # Analytics must never prevent the requested page from loading.
            logger.exception("Unable to record analytics visit")
        return response

