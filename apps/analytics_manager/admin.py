from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.core_manager.admin_mixins import SingletonAdminMixin

from .models import AnalyticsSettings, DailyPageStat, Visit


class SuperuserAnalyticsAdminMixin:
    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AnalyticsSettings)
class AnalyticsSettingsAdmin(
    SingletonAdminMixin, SuperuserAnalyticsAdminMixin, ModelAdmin
):
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            _("Collection"),
            {
                "fields": (
                    "enabled",
                    "collection_mode",
                    "ip_storage_mode",
                    "record_query_string",
                    "exclude_staff",
                    "exclude_bots",
                )
            },
        ),
        (
            _("Privacy and retention"),
            {
                "fields": (
                    "retention_days",
                    "sensitive_query_parameters",
                    "excluded_path_prefixes",
                )
            },
        ),
        (
            _("System"),
            {"classes": ("collapse",), "fields": ("created_at", "updated_at")},
        ),
    )

    def has_add_permission(self, request):
        return bool(request.user.is_superuser and not AnalyticsSettings.objects.exists())

    def changelist_view(self, request, extra_context=None):
        configuration = AnalyticsSettings.get_solo()
        return redirect(
            reverse("admin:analytics_manager_analyticssettings_change", args=[configuration.pk])
        )


@admin.register(Visit)
class VisitAdmin(SuperuserAnalyticsAdminMixin, ModelAdmin):
    list_display = (
        "created_at",
        "path",
        "status_code",
        "view_name",
        "user",
        "ip_display",
    )
    list_filter = ("created_at", "status_code", "app_name", "view_name")
    search_fields = ("path", "query_string", "referrer", "ip_address", "ip_hash")
    date_hierarchy = "created_at"
    list_select_related = ("user",)
    readonly_fields = (
        "created_at",
        "path",
        "query_string",
        "method",
        "status_code",
        "view_name",
        "app_name",
        "user",
        "ip_address",
        "ip_hash",
        "visitor_hash",
        "referrer",
        "user_agent",
    )
    fields = readonly_fields

    @admin.display(description=_("IP / visitor"))
    def ip_display(self, obj):
        return obj.ip_address or (obj.ip_hash[:12] + "…" if obj.ip_hash else "—")

    def get_actions(self, request):
        return {}


@admin.register(DailyPageStat)
class DailyPageStatAdmin(SuperuserAnalyticsAdminMixin, ModelAdmin):
    list_display = ("date", "path", "views", "unique_visitors", "view_name")
    list_filter = ("date", "view_name")
    search_fields = ("path", "view_name")
    date_hierarchy = "date"
    readonly_fields = ("date", "path", "view_name", "views", "unique_visitors")
    fields = readonly_fields

    def get_actions(self, request):
        return {}

