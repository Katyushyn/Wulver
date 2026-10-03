from urllib.parse import urlencode

from django import template
from django.conf import settings
from django.utils.translation import get_language_info


register = template.Library()


@register.filter
def has_admin_actions(value):
    """Ignore whitespace-only content captured from an empty Unfold block."""
    return bool(str(value or "").strip())


def _path_without_language_prefix(path):
    """Return an admin path without any configured non-default language prefix."""
    default_language = settings.LANGUAGE_CODE.lower()

    for code, _name in settings.LANGUAGES:
        code = code.lower()
        if code == default_language:
            continue

        prefix = f"/{code}"
        if path == prefix:
            return "/"
        if path.startswith(f"{prefix}/"):
            return path[len(prefix) :]

    return path or "/"


def _language_url(request, language_code):
    base_path = _path_without_language_prefix(request.path_info)

    if language_code.lower() == settings.LANGUAGE_CODE.lower():
        target_path = base_path
    elif base_path == "/":
        target_path = f"/{language_code}/"
    else:
        target_path = f"/{language_code}{base_path}"

    query_string = urlencode(list(request.GET.lists()), doseq=True)
    return f"{target_path}?{query_string}" if query_string else target_path


@register.simple_tag(takes_context=True)
def admin_language_links(context):
    """Build deterministic admin URLs for prefixed and unprefixed languages."""
    request = context["request"]
    current_language = getattr(request, "LANGUAGE_CODE", settings.LANGUAGE_CODE)

    links = []
    for code, configured_name in settings.LANGUAGES:
        info = get_language_info(code)
        links.append(
            {
                "code": code,
                "name": info.get("name_local") or str(configured_name),
                "url": _language_url(request, code),
                "is_active": code.lower() == current_language.lower(),
            }
        )
    return links
