from django import template
from django.template import Context, Template, TemplateSyntaxError
from django.utils.safestring import mark_safe

from apps.core_manager.models import SiteSettings
from apps.userprofile.models import (
    AuthenticationEmailTemplate,
    AuthenticationSettings,
)


register = template.Library()


@register.simple_tag
def authentication_page_text(page_type):
    # Kept for compatibility with older customized templates. Page wording now
    # belongs directly to the editable authentication template code.
    return None


@register.simple_tag
def authentication_ui():
    auth_settings = AuthenticationSettings.get_solo()
    site_settings = SiteSettings.get_solo()
    return {
        "settings": auth_settings,
        "logo": auth_settings.logo or site_settings.organization_logo,
        "site_name": site_settings.site_name,
    }


@register.simple_tag(takes_context=True)
def authentication_email_content(context, email_type, field):
    email_template = AuthenticationEmailTemplate.objects.filter(
        email_type=email_type
    ).first()
    if email_template is None or field not in {"subject", "message"}:
        return ""

    source = getattr(email_template, field, "") or ""
    try:
        rendered = Template(source).render(
            Context(context.flatten(), autoescape=False)
        )
    except TemplateSyntaxError:
        rendered = source
    return mark_safe(rendered.strip() if field == "subject" else rendered)
