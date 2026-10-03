import json
import logging

from django.http import JsonResponse
from django.core.exceptions import RequestDataTooBig
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache

from apps.ai_assistant.models import AssistantEventLog, AssistantProfile
from apps.ai_assistant.security import (
    ChatAccessDenied,
    ChatRateLimitExceeded,
    check_rate_limits,
    resolve_chat_session,
)
from apps.ai_assistant.services.chat import ask_assistant
from apps.ai_assistant.services.retention import prune_expired_ai_data


logger = logging.getLogger(__name__)
MAX_CHAT_REQUEST_BODY_BYTES = 16 * 1024


def health(request):
    return JsonResponse({"status": "ok"})


@never_cache
@require_POST
def chat_view(request):
    assistant = AssistantProfile.objects.order_by("pk").first()
    if assistant is None or not assistant.is_enabled:
        message = assistant.disabled_message if assistant else "The AI assistant is temporarily unavailable."
        return JsonResponse({"error": str(message)}, status=503)

    if not assistant.allow_anonymous_users and not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication is required."}, status=403)

    prune_expired_ai_data(assistant)

    try:
        if request.content_type != "application/json":
            return JsonResponse({"error": "JSON content type is required."}, status=415)
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
        if content_length > MAX_CHAT_REQUEST_BODY_BYTES:
            return JsonResponse({"error": "Request is too large."}, status=413)
        body = request.body
        if len(body) > MAX_CHAT_REQUEST_BODY_BYTES:
            return JsonResponse({"error": "Request is too large."}, status=413)
        data = json.loads(body.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError

        question = data.get("message", "").strip()
        session_id = data.get("session_id")

        if not question:
            return JsonResponse(
                {"error": "Message is required"},
                status=400,
            )
        if len(question) > assistant.max_message_length:
            return JsonResponse(
                {"error": f"Message must not exceed {assistant.max_message_length} characters."},
                status=400,
            )
        if assistant.require_privacy_consent and data.get("privacy_consent") is not True:
            return JsonResponse({"error": "Privacy consent is required."}, status=400)

        check_rate_limits(request, assistant)
        session = resolve_chat_session(request, assistant, session_id)
        if session.messages.filter(role="user").count() >= assistant.max_messages_per_session:
            raise ChatRateLimitExceeded(3600)

        result = ask_assistant(
            question=question,
            session=session,
            assistant=assistant,
            channel="web",
        )

        return JsonResponse(
            {
                "answer": result["answer"],
                "session_id": str(result["session"].public_id),
            },
            json_dumps_params={"ensure_ascii": False}
        )

    except ChatRateLimitExceeded as error:
        response = JsonResponse({"error": str(assistant.rate_limit_message)}, status=429)
        response["Retry-After"] = str(error.retry_after)
        return response
    except ChatAccessDenied:
        AssistantEventLog.objects.create(
            event_type="security",
            message="Rejected invalid or foreign AI chat session",
        )
        return JsonResponse({"error": "Invalid or expired chat session."}, status=403)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON request."}, status=400)
    except RequestDataTooBig:
        return JsonResponse({"error": "Request is too large."}, status=413)
    except Exception:
        logger.exception("AI assistant request failed")
        AssistantEventLog.objects.create(
            event_type="api_error",
            message="AI assistant request failed; see server logs",
        )
        return JsonResponse(
            {"error": str(assistant.error_message)},
            status=503,
        )
