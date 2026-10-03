from django.conf import settings
from django.db.models import F
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.utils import timezone

from .models import URLRedirect


class URLRedirectMiddleware:
    EXCLUDED_PREFIXES = (
        "/admin/",
        "/uk/admin/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response

        path = request.path_info
        if any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
            return response

        candidate_paths = [path]
        if path != "/" and not path.endswith("/"):
            candidate_paths.append(path + "/")
        redirect = URLRedirect.objects.filter(
            old_path__in=candidate_paths,
            is_active=True,
        ).order_by("id").first()
        if not redirect or redirect.target_url == path:
            return response

        URLRedirect.objects.filter(pk=redirect.pk).update(
            hit_count=F("hit_count") + 1,
            last_used_at=timezone.now(),
        )
        if redirect.status_code == URLRedirect.STATUS_TEMPORARY:
            return HttpResponseRedirect(redirect.target_url)
        return HttpResponsePermanentRedirect(redirect.target_url)


class ContentSecurityPolicyMiddleware:
    """Add the configured CSP header without overwriting an upstream policy."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.CSP_ENABLED:
            return response

        header = (
            "Content-Security-Policy-Report-Only"
            if settings.CSP_REPORT_ONLY
            else "Content-Security-Policy"
        )
        if header not in response:
            response[header] = self._policy_for_request(request)
        return response

    @staticmethod
    def _policy_for_request(request):
        path_parts = [part for part in request.path_info.split("/") if part]
        is_admin = bool(
            path_parts
            and (
                path_parts[0] == "admin"
                or (len(path_parts) > 1 and path_parts[1] == "admin")
            )
        )
        if is_admin:
            return settings.CSP_ADMIN_POLICY
        return settings.CSP_POLICY
