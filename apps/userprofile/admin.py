from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django import forms
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import path, reverse
from django.template import Template, TemplateSyntaxError
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TabbedTranslationAdmin
from unfold.admin import ModelAdmin, StackedInline
from unfold.widgets import UnfoldAdminImageFieldWidget, UnfoldAdminTextareaWidget

from apps.core_manager.admin_mixins import SingletonAdminMixin

from .defaults.authentication_emails import AUTHENTICATION_EMAIL_DEFAULTS

from .models import (
    AuthenticationEmailTemplate,
    AuthenticationSettings,
    AuthenticationTemplate,
    PersonalAccountTemplate,
    UserProfile,
)
from .defaults.personal_account import DEFAULT_PERSONAL_ACCOUNT_TEMPLATE
from .defaults.authentication_templates import get_default_authentication_template


def user_avatar_callback(request):
    user = request.user

    if (
        user
        and user.is_authenticated
        and hasattr(user, "userprofile")
        and user.userprofile.avatar
    ):
        try:
            return user.userprofile.avatar.url
        except ValueError:
            return None

    return None


class UserProfileInline(StackedInline):
    model = UserProfile
    can_delete = False
    fk_name = "user"
    extra = 0
    verbose_name_plural = _("Additional profile options")

    readonly_fields = (
        "share_token",
        "share_token_created",
    )

    fieldsets = (
        (
            _("Avatar"),
            {
                "fields": (
                    "avatar",
                    "prompt",
                )
            },
        ),
        (
            _("Sharing"),
            {
                "fields": (
                    "share_token",
                    "share_token_created",
                ),
                "classes": ("collapse",),
            },
        ),
    )


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    inlines = (
        UserProfileInline,
    )


@admin.register(AuthenticationSettings)
class AuthenticationSettingsAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        return {}

    def changelist_view(self, request, extra_context=None):
        return redirect("admin:userprofile_personalaccounttemplate_change", 1)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        return redirect("admin:userprofile_personalaccounttemplate_change", 1)


class PersonalAccountTemplateAdminForm(forms.ModelForm):
    logo = forms.ImageField(
        label=_("Authentication logo"),
        required=False,
        help_text=_("Falls back to the organization logo from Site settings."),
        widget=UnfoldAdminImageFieldWidget(),
    )
    stylesheet = forms.CharField(
        label=_("Authentication stylesheet"),
        help_text=_("CSS applied to all system authentication pages."),
        widget=UnfoldAdminTextareaWidget(
            attrs={
                "class": "codemirror-auth-css",
                "rows": 32,
                "spellcheck": "false",
            }
        ),
    )

    class Meta:
        model = PersonalAccountTemplate
        fields = "__all__"
        widgets = {
            "code": UnfoldAdminTextareaWidget(
                attrs={
                    "class": "codemirror-personal-account-template",
                    "rows": 40,
                    "spellcheck": "false",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.authentication_settings = AuthenticationSettings.get_solo()

        if not self.is_bound:
            self.initial["logo"] = self.authentication_settings.logo
            self.initial["stylesheet"] = self.authentication_settings.stylesheet

    def save_authentication_settings(self):
        settings = self.authentication_settings

        if "logo" in self.changed_data:
            settings.logo = self.cleaned_data.get("logo") or None

        settings.stylesheet = self.cleaned_data["stylesheet"]
        settings.save()
        return settings


@admin.register(PersonalAccountTemplate)
class PersonalAccountTemplateAdmin(SingletonAdminMixin, ModelAdmin):
    form = PersonalAccountTemplateAdminForm
    change_form_template = "admin/userprofile/personalaccounttemplate/change_form.html"
    fieldsets = (
        (
            _("Appearance"),
            {
                "fields": (
                    "logo",
                    "stylesheet",
                )
            },
        ),
        (
            _("Personal account template"),
            {
                "fields": (
                    "code",
                )
            },
        ),
        (
            _("System"),
            {
                "classes": ("collapse",),
                "fields": ("updated_at",),
            },
        ),
    )
    readonly_fields = ("updated_at",)

    class Media:
        css = {
            "all": (
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css",
                "theme_manager/css/authentication-css-editor.css",
            )
        }
        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/xml/xml.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js",
            "theme_manager/js/authentication-css-editor.js",
            "userprofile/js/personal-account-template-editor.js",
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        form.save_authentication_settings()

    def has_add_permission(self, request):
        return not PersonalAccountTemplate.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = PersonalAccountTemplate.get_solo()
        return redirect(
            "admin:userprofile_personalaccounttemplate_change",
            obj.pk,
        )

    def get_urls(self):
        return [
            path(
                "<int:object_id>/reset-to-defaults/",
                self.admin_site.admin_view(self.reset_to_defaults_view),
                name="userprofile_personalaccounttemplate_reset_defaults",
            ),
        ] + super().get_urls()

    def reset_to_defaults_view(self, request, object_id):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        obj = self.get_object(request, str(object_id))
        if obj is None or not self.has_change_permission(request, obj):
            raise Http404

        obj.code = DEFAULT_PERSONAL_ACCOUNT_TEMPLATE
        obj.save(update_fields=("code", "updated_at"))
        messages.success(
            request,
            _("Personal account template was reset to its default."),
        )
        return redirect(
            "admin:userprofile_personalaccounttemplate_change",
            obj.pk,
        )


class AuthenticationTemplateAdminForm(forms.ModelForm):
    class Meta:
        model = AuthenticationTemplate
        fields = "__all__"
        widgets = {
            "code": UnfoldAdminTextareaWidget(
                attrs={
                    "class": "codemirror-authentication-template",
                    "rows": 40,
                    "spellcheck": "false",
                }
            ),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code") or ""

        try:
            Template(code)
        except TemplateSyntaxError as error:
            raise forms.ValidationError(
                _("Invalid Django template syntax: %(error)s"),
                params={"error": error},
            ) from error

        return code


@admin.register(AuthenticationTemplate)
class AuthenticationTemplateAdmin(ModelAdmin):
    form = AuthenticationTemplateAdminForm
    change_form_template = "admin/userprofile/authenticationtemplate/change_form.html"
    list_display = ("template_name", "updated_at")
    list_filter = ("template_name",)
    search_fields = ("template_name", "code")
    readonly_fields = ("updated_at",)
    fields = ("template_name", "code", "updated_at")

    class Media:
        css = {
            "all": (
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css",
                "theme_manager/css/authentication-css-editor.css",
            )
        }
        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/xml/xml.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js",
            "userprofile/js/authentication-template-editor.js",
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [
            path(
                "<int:object_id>/reset-to-defaults/",
                self.admin_site.admin_view(self.reset_to_defaults_view),
                name="userprofile_authenticationtemplate_reset_defaults",
            ),
        ] + super().get_urls()

    def reset_to_defaults_view(self, request, object_id):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        obj = self.get_object(request, str(object_id))
        if obj is None or not self.has_change_permission(request, obj):
            raise Http404

        obj.code = get_default_authentication_template(obj.template_name)
        obj.save(update_fields=("code", "updated_at"))
        messages.success(
            request,
            _("Authentication template was reset to its default."),
        )
        return redirect(
            "admin:userprofile_authenticationtemplate_change",
            obj.pk,
        )


@admin.register(AuthenticationEmailTemplate)
class AuthenticationEmailTemplateAdmin(ModelAdmin, TabbedTranslationAdmin):
    change_form_template = "admin/userprofile/authenticationemailtemplate/change_form.html"
    list_display = ("email_type", "subject", "updated_at")
    search_fields = ("subject", "message")
    readonly_fields = ("updated_at",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email_type",
                    "subject",
                    "message",
                    "updated_at",
                )
            },
        ),
    )

    def get_urls(self):
        return [
            path(
                "<int:object_id>/reset-to-defaults/",
                self.admin_site.admin_view(self.reset_to_defaults_view),
                name="userprofile_authenticationemailtemplate_reset_defaults",
            ),
        ] + super().get_urls()

    def reset_to_defaults_view(self, request, object_id):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        email_template = self.get_object(request, str(object_id))
        if email_template is None:
            raise Http404
        if not self.has_change_permission(request, email_template):
            raise Http404

        defaults = AUTHENTICATION_EMAIL_DEFAULTS.get(email_template.email_type)
        if defaults is None:
            messages.error(request, _("Default email template was not found."))
        else:
            email_template.subject_en, email_template.message_en = defaults["en"]
            email_template.subject_uk, email_template.message_uk = defaults["uk"]
            email_template.subject = email_template.subject_en
            email_template.message = email_template.message_en
            email_template.save(
                update_fields=(
                    "subject",
                    "subject_en",
                    "subject_uk",
                    "message",
                    "message_en",
                    "message_uk",
                    "updated_at",
                )
            )
            messages.success(
                request,
                _("Authentication email template was reset to its defaults."),
            )

        return redirect(
            reverse(
                "admin:userprofile_authenticationemailtemplate_change",
                args=[email_template.pk],
            )
        )
