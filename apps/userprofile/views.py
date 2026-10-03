from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template import RequestContext, Template, TemplateSyntaxError

from apps.core_manager.seo import build_seo_context
from .defaults.personal_account import DEFAULT_PERSONAL_ACCOUNT_TEMPLATE
from .models import AuthenticationSettings, PersonalAccountTemplate


def authentication_stylesheet(request):
    response = HttpResponse(
        AuthenticationSettings.get_solo().stylesheet,
        content_type="text/css; charset=utf-8",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def personal_account(request):
    account_template = PersonalAccountTemplate.get_solo()
    context = build_seo_context(request)
    context.update(
        {
            "title": "Personal account",
            "description": "Manage your personal account settings.",
            "robots": "noindex, nofollow",
            "personal_account_template": account_template,
        }
    )

    try:
        template = Template(account_template.code)
    except TemplateSyntaxError:
        template = Template(DEFAULT_PERSONAL_ACCOUNT_TEMPLATE)

    return HttpResponse(template.render(RequestContext(request, context)))
