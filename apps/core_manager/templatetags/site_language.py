from django import template
from django.utils.translation import get_language
from django.urls import translate_url
from django.conf import settings

register = template.Library()


@register.simple_tag(takes_context=True)
def site_language_links(context):
    request = context.get("request")
    if request is None:
        return []
    current = get_language()
    return [
        {"code": code, "name": name,
         "url": translate_url(request.get_full_path(), code),
         "is_active": code == current}
        for code, name in settings.LANGUAGES
    ]
