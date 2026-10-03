from django import template

from apps.ai_assistant.models import AssistantProfile


register = template.Library()


@register.simple_tag
def ai_assistant_profile():
    return AssistantProfile.objects.order_by("pk").first()
