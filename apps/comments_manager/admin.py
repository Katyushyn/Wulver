from django import forms
from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.shortcuts import redirect
from django.urls import path
from django.utils.translation import gettext_lazy as _
from django_comments.models import Comment
from modeltranslation.admin import TabbedTranslationAdmin
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.core_manager.admin_mixins import SingletonAdminMixin

from .defaults import (
    DEFAULT_COMMENT_STYLESHEET,
    DEFAULT_COMMENT_TEMPLATES,
    DEFAULT_COMMENT_TEXTS,
)
from .models import CommentSettings, CommentTemplate


class CommentSettingsAdminForm(forms.ModelForm):
    class Meta:
        model = CommentSettings
        fields = "__all__"
        widgets = {
            "stylesheet": UnfoldAdminTextareaWidget(
                attrs={"class": "codemirror-comment-css", "rows": 32, "spellcheck": "false"}
            ),
        }


class CommentTemplateAdminForm(forms.ModelForm):
    class Meta:
        model = CommentTemplate
        fields = "__all__"
        widgets = {
            "code": UnfoldAdminTextareaWidget(
                attrs={"class": "codemirror-comment-template", "rows": 36, "spellcheck": "false"}
            ),
        }


try:
    admin.site.unregister(Comment)
except NotRegistered:
    pass


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = (
        "user_name", "user_email", "content_type", "object_pk",
        "is_public", "is_removed", "submit_date",
    )
    list_filter = ("is_public", "is_removed", "submit_date", "content_type", "site")
    search_fields = (
        "user_name", "user_email", "user_url", "comment", "object_pk",
        "ip_address",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("submit_date", "ip_address")
    fields = (
        "content_type", "object_pk", "site", "user", "user_name",
        "user_email", "user_url", "comment", "is_public", "is_removed",
        "submit_date", "ip_address",
    )
    actions = ("approve_comments", "hide_comments", "mark_removed")

    @admin.action(description=_("Approve selected comments"))
    def approve_comments(self, request, queryset):
        updated = queryset.update(is_public=True, is_removed=False)
        self.message_user(
            request,
            _("Approved %(count)s comment(s).") % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Hide selected comments"))
    def hide_comments(self, request, queryset):
        updated = queryset.update(is_public=False)
        self.message_user(
            request,
            _("Hidden %(count)s comment(s).") % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=_("Mark selected comments as removed"))
    def mark_removed(self, request, queryset):
        updated = queryset.update(is_public=False, is_removed=True)
        self.message_user(
            request,
            _("Removed %(count)s comment(s).") % {"count": updated},
            messages.SUCCESS,
        )


@admin.register(CommentSettings)
class CommentSettingsAdmin(SingletonAdminMixin, ModelAdmin, TabbedTranslationAdmin):
    form = CommentSettingsAdminForm
    change_form_template = "admin/comments_manager/commentsettings/change_form.html"
    readonly_fields = ("updated_at",)
    fieldsets = (
        (_("Posting and moderation"), {"fields": (
            "allow_anonymous_comments", "publication_mode",
            "rate_limit_count", "rate_limit_window_minutes",
        )}),
        (_("Texts"), {"fields": ("form_title", "comment_label", "comment_placeholder", "submit_text", "empty_text")}),
        (_("Styles"), {"fields": ("stylesheet",)}),
        (_("System"), {"fields": ("updated_at",), "classes": ("collapse",)}),
    )

    class Media:
        css = {"all": (
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css",
            "theme_manager/css/authentication-css-editor.css",
        )}
        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js",
            "comments_manager/js/comment-css-editor.js",
        )

    def has_add_permission(self, request):
        return not CommentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = CommentSettings.get_solo()
        return redirect("admin:comments_manager_commentsettings_change", obj.pk)

    def get_urls(self):
        return [
            path(
                "<int:object_id>/reset-to-defaults/",
                self.admin_site.admin_view(self.reset_to_defaults_view),
                name="comments_manager_commentsettings_reset_defaults",
            )
        ] + super().get_urls()

    def reset_to_defaults_view(self, request, object_id):
        if request.method != "POST":
            return redirect("admin:comments_manager_commentsettings_change", object_id)
        obj = self.get_object(request, str(object_id))
        if obj is None or not self.has_change_permission(request, obj):
            return redirect("admin:index")
        for language, values in DEFAULT_COMMENT_TEXTS.items():
            for field_name, value in values.items():
                setattr(obj, f"{field_name}_{language}", value)
        for field_name, value in DEFAULT_COMMENT_TEXTS["en"].items():
            setattr(obj, field_name, value)
        obj.stylesheet = DEFAULT_COMMENT_STYLESHEET
        obj.save()
        self.message_user(request, _("Comment appearance was reset to defaults."), messages.SUCCESS)
        return redirect("admin:comments_manager_commentsettings_change", obj.pk)


@admin.register(CommentTemplate)
class CommentTemplateAdmin(ModelAdmin):
    form = CommentTemplateAdminForm
    change_form_template = "admin/comments_manager/commenttemplate/change_form.html"
    list_display = ("template_type", "updated_at")
    readonly_fields = ("updated_at",)
    fields = ("template_type", "code", "updated_at")

    class Media:
        css = {"all": (
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css",
            "theme_manager/css/authentication-css-editor.css",
        )}
        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/xml/xml.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js",
            "comments_manager/js/comment-template-html-editor.js",
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [
            path(
                "<int:object_id>/reset-to-defaults/",
                self.admin_site.admin_view(self.reset_view),
                name="comments_manager_commenttemplate_reset_defaults",
            )
        ] + super().get_urls()

    def reset_view(self, request, object_id):
        obj = self.get_object(request, str(object_id))
        if request.method == "POST" and obj and self.has_change_permission(request, obj):
            obj.code = DEFAULT_COMMENT_TEMPLATES[obj.template_type]
            obj.save(update_fields=("code", "updated_at"))
            self.message_user(request, _("Comment template was reset to defaults."), messages.SUCCESS)
        return redirect("admin:comments_manager_commenttemplate_change", object_id)
