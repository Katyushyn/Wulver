from datetime import timedelta

from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.signing import salted_hmac
from django.db.models import Q, Sum
from django.utils import timezone

from .models import AssistantEventLog, ChatMessage, ChatSession


class ChatAccessDenied(Exception):
    pass


class ChatRateLimitExceeded(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, int(retry_after))
        super().__init__("AI assistant rate limit exceeded")


def get_client_ip(request):
    if settings.AI_ASSISTANT_TRUST_X_FORWARDED_FOR:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()[:45]
    # REMOTE_ADDR cannot be forged with a request header.
    return (request.META.get("REMOTE_ADDR") or "").strip()[:45]


def get_client_hash(request):
    ip_address = get_client_ip(request)
    return salted_hmac("ai-assistant-client", ip_address or "unknown").hexdigest()


def ensure_browser_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def resolve_chat_session(request, assistant, public_id=None):
    browser_session_key = ensure_browser_session_key(request)
    client_hash = get_client_hash(request)
    user = request.user if request.user.is_authenticated else None

    if public_id:
        try:
            session = ChatSession.objects.get(public_id=public_id, assistant=assistant)
        except (ChatSession.DoesNotExist, ValidationError, ValueError):
            raise ChatAccessDenied from None

        belongs_to_browser = session.browser_session_key == browser_session_key
        belongs_to_user = bool(user and session.user_id == user.pk)
        if not belongs_to_browser and not belongs_to_user:
            raise ChatAccessDenied
        if session.is_closed:
            raise ChatAccessDenied
        if session.created_at < timezone.now() - timedelta(hours=assistant.session_lifetime_hours):
            session.is_closed = True
            session.save(update_fields=("is_closed",))
            raise ChatAccessDenied
        return session

    return ChatSession.objects.create(
        assistant=assistant,
        channel="web",
        browser_session_key=browser_session_key,
        client_hash=client_hash,
        user=user,
        ip_address=get_client_ip(request) if assistant.store_ip_addresses else None,
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:1000],
        last_message_at=timezone.now(),
    )


def check_rate_limits(request, assistant, session=None):
    now = timezone.now()
    user_messages = ChatMessage.objects.filter(role="user")
    visitor_filter = Q(session__client_hash=get_client_hash(request))
    if request.user.is_authenticated:
        visitor_filter |= Q(session__user=request.user)

    limits = (
        (assistant.requests_per_minute, timedelta(minutes=1), 60),
        (assistant.requests_per_hour, timedelta(hours=1), 3600),
        (assistant.requests_per_day, timedelta(days=1), 86400),
    )
    for limit, window, retry_after in limits:
        if user_messages.filter(visitor_filter, created_at__gte=now - window).count() >= limit:
            _log_rate_limit(session, "visitor", limit)
            raise ChatRateLimitExceeded(retry_after)

    if user_messages.filter(created_at__gte=now - timedelta(days=1)).count() >= assistant.global_requests_per_day:
        _log_rate_limit(session, "global", assistant.global_requests_per_day)
        raise ChatRateLimitExceeded(3600)

    day_tokens = ChatMessage.objects.filter(created_at__gte=now - timedelta(days=1)).aggregate(total=Sum("total_tokens"))["total"] or 0
    if day_tokens >= assistant.daily_token_limit:
        _log_rate_limit(session, "daily_tokens", assistant.daily_token_limit)
        raise ChatRateLimitExceeded(3600)

    month_tokens = ChatMessage.objects.filter(created_at__gte=now - timedelta(days=30)).aggregate(total=Sum("total_tokens"))["total"] or 0
    if month_tokens >= assistant.monthly_token_limit:
        _log_rate_limit(session, "monthly_tokens", assistant.monthly_token_limit)
        raise ChatRateLimitExceeded(86400)

    if session is not None and session.messages.filter(role="user").count() >= assistant.max_messages_per_session:
        _log_rate_limit(session, "session", assistant.max_messages_per_session)
        raise ChatRateLimitExceeded(3600)


def _log_rate_limit(session, scope, limit):
    AssistantEventLog.objects.create(
        session=session,
        event_type="rate_limit",
        message=f"Request blocked by {scope} rate limit",
        data={"scope": scope, "limit": limit},
    )
