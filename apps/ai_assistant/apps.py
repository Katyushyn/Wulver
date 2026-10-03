from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AiAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_assistant"
    verbose_name = _("AI assistant")
