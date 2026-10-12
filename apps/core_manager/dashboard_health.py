from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language, gettext as _


CACHE_SECONDS = 300
BACKUP_MAX_AGE_DAYS = 7
AI_ERROR_WINDOW_HOURS = 24


def _warning(severity, title, description, url, count=None):
    return {
        "severity": severity,
        "title": str(title),
        "description": str(description),
        "url": url,
        "count": count,
    }


def _build_warnings():
    from django_comments.models import Comment

    from apps.ai_assistant.models import AssistantEventLog
    from apps.backup_manager.models import BackupSnapshot
    from apps.blog_manager.models import Article, BlogSettings
    from apps.theme_manager.models import TemplateType, Theme, ThemeTemplate

    from .models import SiteSettings

    warnings = []
    now = timezone.now()

    backup_url = reverse("admin:backup_manager_backupsnapshot_changelist")
    last_backup = BackupSnapshot.objects.filter(
        status=BackupSnapshot.Status.COMPLETED
    ).order_by("-completed_at", "-created_at").first()
    latest_failed = BackupSnapshot.objects.filter(
        status=BackupSnapshot.Status.FAILED
    ).order_by("-created_at").first()
    if last_backup is None:
        warnings.append(_warning(
            "error",
            _("No completed backup"),
            _("Create a full backup before making important production changes."),
            backup_url,
        ))
    else:
        completed = last_backup.completed_at or last_backup.created_at
        if completed < now - timedelta(days=BACKUP_MAX_AGE_DAYS):
            warnings.append(_warning(
                "warning",
                _("The latest backup is older than 7 days"),
                _("Create a fresh backup and verify that scheduled backups are running."),
                backup_url,
            ))
        if not last_backup.archive_exists:
            warnings.append(_warning(
                "error",
                _("The latest backup archive is missing"),
                _("The database record exists, but its archive cannot be found on disk."),
                backup_url,
            ))
    if latest_failed and (
        last_backup is None or latest_failed.created_at > (last_backup.completed_at or last_backup.created_at)
    ):
        warnings.append(_warning(
            "error",
            _("The most recent backup attempt failed"),
            _("Open the backup record and review its error message."),
            backup_url,
        ))

    missing_images = Article.objects.filter(
        is_published=True,
        publish__lte=now,
    ).filter(
        Q(img_crop="") | Q(img_crop__isnull=True) |
        Q(img_crop_mob="") | Q(img_crop_mob__isnull=True)
    ).count()
    if missing_images:
        warnings.append(_warning(
            "warning",
            _("Published articles without complete optimized images"),
            _("These articles are missing a desktop or mobile cropped image."),
            reverse("admin:blog_manager_article_changelist") + "?is_published__exact=1",
            missing_images,
        ))

    comments_pending = Comment.objects.filter(
        is_public=False,
        is_removed=False,
    ).count()
    if comments_pending:
        warnings.append(_warning(
            "warning",
            _("Comments are awaiting moderation"),
            _("Review these comments and publish or remove them."),
            reverse("admin:django_comments_comment_changelist") + "?is_public__exact=0&is_removed__exact=0",
            comments_pending,
        ))

    ai_errors = AssistantEventLog.objects.filter(
        event_type__in=("error", "api_error"),
        created_at__gte=now - timedelta(hours=AI_ERROR_WINDOW_HOURS),
    ).count()
    if ai_errors:
        warnings.append(_warning(
            "error",
            _("Recent AI assistant errors"),
            _("Errors or provider API failures were recorded during the last 24 hours."),
            reverse("admin:ai_assistant_assistanteventlog_changelist"),
            ai_errors,
        ))

    site = SiteSettings.get_solo()
    site_url = reverse("admin:core_manager_sitesettings_change", args=[site.pk])
    if not site.home_page_id or not site.home_page.is_published or not site.home_page.template_id:
        warnings.append(_warning(
            "error",
            _("The public homepage is not ready"),
            _("Choose a published home page with an active template."),
            site_url,
        ))
    if not site.search_template_id:
        warnings.append(_warning(
            "warning",
            _("Search template is not configured"),
            _("Search results cannot use the intended site design."),
            site_url,
        ))
    if not site.error_404_template_id:
        fallback_404_exists = ThemeTemplate.objects.filter(
            template_type=TemplateType.ERROR_TEMPLATE,
            is_active=True,
            theme__is_active=True,
        ).exists()
        if fallback_404_exists:
            warnings.append(_warning(
                "warning",
                _("404 template is selected automatically"),
                _(
                    "An active 404 template is being used as a fallback, but it is not "
                    "explicitly selected in Site Settings."
                ),
                site_url,
            ))
        else:
            warnings.append(_warning(
                "error",
                _("404 template is not available"),
                _("Create an active 404 template and select it in Site Settings."),
                site_url,
            ))
    if not Theme.objects.filter(is_active=True).exists():
        warnings.append(_warning(
            "error",
            _("No active theme"),
            _("Activate a theme before publishing the site."),
            reverse("admin:theme_manager_theme_changelist"),
        ))

    blog = BlogSettings.get_solo()
    # A dedicated paginated template is optional: category rendering explicitly
    # falls back to the normal category template when it is not configured.
    missing_blog_templates = sum(not value for value in (
        blog.default_category_template_id,
        blog.default_article_template_id,
    ))
    if missing_blog_templates:
        warnings.append(_warning(
            "warning",
            _("Default blog templates are incomplete"),
            _("Configure the default category and article templates."),
            reverse("admin:blog_manager_blogsettings_change", args=[blog.pk]),
            missing_blog_templates,
        ))

    if not settings.DEBUG:
        production_problems = []
        if not settings.SESSION_COOKIE_SECURE:
            production_problems.append("SESSION_COOKIE_SECURE")
        if not settings.CSRF_COOKIE_SECURE:
            production_problems.append("CSRF_COOKIE_SECURE")
        if settings.SECURE_HSTS_SECONDS <= 0:
            production_problems.append("SECURE_HSTS_SECONDS")
        if not settings.ALLOWED_HOSTS or "*" in settings.ALLOWED_HOSTS:
            production_problems.append("ALLOWED_HOSTS")
        if len(settings.SECRET_KEY) < 50 or settings.SECRET_KEY == "unsafe-dev-secret-key":
            production_problems.append("SECRET_KEY")
        if production_problems:
            warnings.append(_warning(
                "error",
                _("Production security settings require attention"),
                _("Review: %(settings)s") % {"settings": ", ".join(production_problems)},
                reverse("admin:index") + "#wulver-environment-form",
                len(production_problems),
            ))

    severity_order = {"error": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda item: (severity_order[item["severity"]], item["title"]))
    return warnings


def dashboard_health_context(request, refresh=False):
    if not request.user.is_active or not request.user.is_superuser:
        return None
    language = get_language() or settings.LANGUAGE_CODE
    key = f"dashboard-health:v1:{language}"
    if refresh:
        cache.delete(key)
    warnings = cache.get(key)
    if warnings is None:
        warnings = _build_warnings()
        cache.set(key, warnings, CACHE_SECONDS)
    # Configuration presence is checked on every request, independently of the
    # cached database checks. Never put the credential itself into the context.
    warnings = list(warnings)
    if not (getattr(settings, "OPENAI_API_KEY", "") or "").strip():
        warnings.append(_warning(
            "warning",
            _("OpenAI API key is not configured"),
            _("AI features that use the OpenAI API cannot work without a key. Add OPENAI_API_KEY in Environment configuration."),
            reverse("admin:index") + "#env-OPENAI_API_KEY",
        ))
    return {
        "warnings": warnings,
        "errors": sum(item["severity"] == "error" for item in warnings),
        "warning_count": sum(item["severity"] == "warning" for item in warnings),
        "refresh_url": reverse("admin:index") + "?health_refresh=1#site-attention",
    }

