from urllib.parse import urlencode

from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def authentication_button_url(context):
    request = context.get("request")
    user = getattr(request, "user", None)

    if user and user.is_authenticated:
        return reverse("personal_account")

    login_url = reverse("account_login")
    if not request:
        return login_url
    return f"{login_url}?{urlencode({'next': request.get_full_path()})}"
