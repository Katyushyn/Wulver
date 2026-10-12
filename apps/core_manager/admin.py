from django.contrib import admin, messages


from django import forms
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TabbedTranslationAdmin

from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.theme_manager.models import ThemeTemplate, TemplateType
from apps.core_manager.admin_mixins import SingletonAdminMixin
from apps.core_manager.forms import PageAdminForm, SiteSettingsAdminForm
from apps.core_manager.models import (
    ContactMessage,
    URLLink,
    NewsletterSubscription,
    Page,
    SitemapSettings,
    SiteSettings,
    URLRedirect,
)
@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdmin):
    actions = ('mark_read', 'mark_unread')

    @admin.action(description=_("Mark as read"))
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description=_("Mark as unread"))
    def mark_unread(self, request, queryset):
        queryset.update(is_read=False)

    list_display = (
        "subject",
        "name",
        "email",
        "is_read",
        "ip_address",
        "created_at",
    )
    list_filter = (
        "is_read",
        "created_at",
    )
    search_fields = (
        "name",
        "email",
        "subject",
        "message",
        "source_url",
        "ip_address",
    )
    readonly_fields = (
        "source_url",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
    )
    fields = (
        "name",
        "email",
        "subject",
        "message",
        "is_read",
        "source_url",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
    )


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(ModelAdmin):
    list_display = (
        "email",
        "is_active",
        "source_url",
        "ip_address",
        "created_at",
    )
    list_filter = (
        "is_active",
        "created_at",
    )
    search_fields = (
        "email",
        "source_url",
        "ip_address",
        "user_agent",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    fields = (
        "email",
        "is_active",
        "source_url",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
    )


@admin.register(URLRedirect)
class URLRedirectAdmin(ModelAdmin):
    list_display = (
        "old_path",
        "target_url",
        "status_code",
        "is_active",
        "is_automatic",
        "hit_count",
        "last_used_at",
    )
    list_filter = (
        "status_code",
        "is_active",
        "is_automatic",
        "created_at",
    )
    search_fields = (
        "old_path",
        "target_url",
        "note",
    )
    readonly_fields = (
        "is_automatic",
        "hit_count",
        "last_used_at",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            _("Redirect"),
            {
                "fields": (
                    "old_path",
                    "target_url",
                    "status_code",
                    "is_active",
                    "note",
                )
            },
        ),
        (
            _("Statistics"),
            {
                "fields": (
                    "is_automatic",
                    "hit_count",
                    "last_used_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_automatic:
            fields.append("old_path")
        return tuple(fields)


@admin.register(SiteSettings)
class SiteSettingsAdmin(SingletonAdminMixin, ModelAdmin):
    form = SiteSettingsAdminForm
    change_form_template = "admin/help/change_form.html"

    list_display = (
        "site_name",
        "site_domain",
        "site_url",
        "maintenance_mode",
        "updated_at",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            _("General"),
            {
                "fields": (
                    "site_name",
                    "site_domain",
                    "site_url",
                    "home_page",
                )
            },
        ),
        (
            _("Contacts"),
            {
                "fields": (
                    "contact_email",
                    "contact_phone",
                    "contact_rate_limit",
                    "contact_rate_window",
                    "contact_message_max_length",
                )
            },
        ),
        (
            _("Newsletter security"),
            {
                "fields": (
                    "newsletter_require_confirmation",
                    "newsletter_rate_limit",
                    "newsletter_rate_window",
                    "newsletter_confirmation_rate_limit",
                    "newsletter_confirmation_rate_window",
                    "newsletter_confirmation_token_ttl",
                )
            },
        ),
        (
            _("External reviews"),
            {
                "fields": (
                    "reviews_enabled",
                    "reviews_limit",
                    "reviews_cache_timeout",
                    "github_reviews_enabled",
                    "github_reviews_repository",
                    "github_reviews_issue_number",
                    "github_reviews_timeout",
                )
            },
        ),
        (
            _("Error pages"),
            {
                "fields": (
                    "error_404_template",
                )
            },
        ),
        (
            _("Search"),
            {
                "fields": (
                    "search_template",
                )
            },
        ),
        (
            _("SEO"),
            {
                "fields": (
                    "title",
                    "description",
                    "default_preview_image",
                    "default_image_alt",
                    "theme_color",
                    "robots_txt",
                )
            },
        ),
        (
            _("Favicons"),
            {
                "fields": (
                    "favicon_ico",
                    "favicon_png",
                    "apple_touch_icon",
                )
            },
        ),
        (
            _("Integrations"),
            {
                "fields": (
                    "google_analytics_id",
                    "google_tag_manager_id",
                )
            },
        ),
        (
            _("Social networks"),
            {
                "fields": (
                    "twitter_handle",
                    "x_url",
                    "facebook_url",
                    "instagram_url",
                    "linkedin_url",
                    "youtube_url",
                    "tiktok_url",
                    "telegram_url",
                    "whatsapp_url",
                )
            },
        ),
        (
            _("Social and schema"),
            {
                "fields": (
                    "author_name",
                    "og_site_name",
                    "default_og_type",
                    "organization_name",
                    "organization_logo",
                    "person_name",
                    "person_job_title",
                    "same_as_links",
                    "person_image",
                    "default_schema_graph",
                    "canonical_allowed_params",
                )
            },
        ),
        (
            _("Maintenance"),
            {
                "fields": (
                    "maintenance_mode",
                    "maintenance_message",
                )
            },
        ),
        (
            _("System"),
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        template_types = {
            "error_404_template": TemplateType.ERROR_TEMPLATE,
            "search_template": TemplateType.SEARCH_PAGE,
        }
        if db_field.name in template_types:
            kwargs["queryset"] = ThemeTemplate.objects.filter(
                theme__is_active=True,
                template_type=template_types[db_field.name],
                is_active=True,
            ).select_related("theme")

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        site_settings = SiteSettings.get_solo()

        return redirect(
            reverse(
                "admin:core_manager_sitesettings_change",
                args=[site_settings.pk],
            )
        )


@admin.register(SitemapSettings)
class SitemapSettingsAdmin(SingletonAdminMixin, ModelAdmin):
    change_form_template = "admin/core_manager/sitemapsettings/change_form.html"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            _("Content"),
            {
                "fields": (
                    "enabled",
                    "include_homepage",
                    "include_pages",
                    "include_categories",
                    "include_articles",
                )
            },
        ),
        (
            _("Languages"),
            {"fields": ("include_translations", "include_alternates")},
        ),
        (
            _("Priorities"),
            {
                "fields": (
                    "homepage_priority",
                    "page_priority",
                    "category_priority",
                    "article_priority",
                )
            },
        ),
        (_("Cache"), {"fields": ("cache_timeout",)}),
        (
            _("System"),
            {"classes": ("collapse",), "fields": ("created_at", "updated_at")},
        ),
    )

    def has_add_permission(self, request):
        return not SitemapSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        configuration = SitemapSettings.get_solo()
        return redirect(
            reverse(
                "admin:core_manager_sitemapsettings_change",
                args=[configuration.pk],
            )
        )

    def get_urls(self):
        return [
            path(
                "clear-cache/",
                self.admin_site.admin_view(self.clear_cache_view),
                name="core_manager_sitemapsettings_clear_cache",
            ),
            *super().get_urls(),
        ]

    def clear_cache_view(self, request):
        if request.method != "POST":
            return redirect(
                "admin:core_manager_sitemapsettings_change",
                SitemapSettings.get_solo().pk,
            )
        from .sitemaps import invalidate_sitemap_cache

        invalidate_sitemap_cache()
        messages.success(request, _("Sitemap cache was cleared."))
        return redirect(
            "admin:core_manager_sitemapsettings_change",
            SitemapSettings.get_solo().pk,
        )


@admin.register(Page)
class PageAdmin(ModelAdmin, TabbedTranslationAdmin):
    form = PageAdminForm

    def get_model_perms(self, request):
        """Keep the legacy admin URL available without duplicating the menu entry."""
        return {}

    list_display = (
        "title",
        "slug",
        "template",
        "is_published",
        "noindex",
        "updated_at",
    )
    list_filter = (
        "is_published",
        "noindex",
        "template",
    )
    search_fields = (
        "title",
        "slug",
        "description",
    )
    prepopulated_fields = {
        "slug": ("title",),
    }
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            _("General"),
            {
                "fields": (
                    "title",
                    "slug",
                    "description",
                    "keywords",
                    "template",
                    "seo_title",
                    "is_published",
                )
            },
        ),
        (
            _("SEO"),
            {
                "fields": (
                    "preview_image",
                    "og_type",
                    "schema_graph",
                    "noindex",
                )
            },
        ),
        (
            _("System"),
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "template":
            kwargs["queryset"] = ThemeTemplate.objects.filter(
                theme__is_active=True,
                template_type=TemplateType.CHILDREN_PAGE,
                is_active=True,
            )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

@admin.register(URLLink)
class URLLinkAdmin(ModelAdmin):
    list_display = (
        "title",
        "url",
        "open_in_new_tab",
        "nofollow",
        "is_active",
    )
    list_filter = (
        "open_in_new_tab",
        "nofollow",
        "is_active",
    )
    search_fields = (
        "title",
        "url",
    )
