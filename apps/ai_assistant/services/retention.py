from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from apps.ai_assistant.models import AssistantEventLog, ChatSession, Lead


def prune_expired_ai_data(assistant, force=False):
    cache_key = f"ai-assistant-retention:{assistant.pk}"
    if not force and not cache.add(cache_key, True, timeout=86400):
        return None

    cutoff = timezone.now() - timedelta(days=assistant.conversation_retention_days)
    lead_count, _ = Lead.objects.filter(updated_at__lt=cutoff).delete()
    session_count, _ = ChatSession.objects.filter(created_at__lt=cutoff).delete()
    log_count, _ = AssistantEventLog.objects.filter(created_at__lt=cutoff).delete()
    return {
        "sessions": session_count,
        "leads": lead_count,
        "logs": log_count,
    }
