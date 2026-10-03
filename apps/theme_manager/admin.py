from django import forms
from django.utils.translation import gettext, gettext_lazy as _
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from unfold.widgets import (
    UnfoldAdminImageFieldWidget,
    UnfoldAdminTextareaWidget,
    UnfoldAdminTextInputWidget,
    UnfoldBooleanSwitchWidget,
)
from pathlib import Path
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.db.models import Case, IntegerField, Q, Value, When
from django.urls import path, reverse
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from bs4 import BeautifulSoup
from openai import OpenAI
from django.contrib import messages
from django.shortcuts import redirect
from .models import (
    TemplateComponent,
    Theme,
    ThemeTemplate,
    ThemeTemplateVersion,
    TemplateType,
)
from .forms.theme_html_upload import ThemeZipUploadForm
from apps.blog_manager.models import (
    Article,
    Category,
    ImageModule,
    LatestArticlesModule,
    TagModule,
)
from apps.core_manager.models import Page, SiteSettings
from apps.core_manager.admin_links import get_cms_link_options
from apps.core_manager.image_processing import SOCIAL_PREVIEW_SPEC, process_uploaded_image
from apps.theme_manager.ai_image_generator import (
    ImageGenerationError,
    generate_replacement_image,
)
from apps.theme_manager.template_load_analyzer import analyze_template_loads
from apps.theme_manager.template_versions import save_template_code
from apps.theme_manager.template_formatter import format_template_code
from apps.theme_manager.css_class_scanner import collect_template_css_classes
from apps.theme_manager.asset_browser import (
    AssetUploadError,
    collect_image_assets,
    delete_image_assets,
    save_uploaded_image,
)
from django.core.files.storage import FileSystemStorage
import shutil
import zipfile
from django.utils.text import slugify
from modeltranslation.admin import TabbedTranslationAdmin
import re
import json
import difflib
from unidecode import unidecode


# class ThemeTemplateInline(TabularInline):
#     model = ThemeTemplate
#     extra = 0
#     fields = (
#         "name",
#         "template_type",
#         "file_path",
#         "is_active",
#         "updated_at",
#     )
#     readonly_fields = ("updated_at",)
#     show_change_link = True


@admin.register(TemplateComponent)
class TemplateComponentAdmin(ModelAdmin):
    filter_horizontal = (
        "latest_articles_modules",
        "tag_modules",
        "image_modules",
    )
    list_display = (
        "name",
        "category",
        "slug",
        "is_active",
        "sort_order",
        "updated_at",
    )
    list_filter = (
        "category",
        "is_active",
    )
    search_fields = (
        "name",
        "slug",
        "category",
        "description",
        "code",
        "ai_conversion_prompt",
    )
    prepopulated_fields = {
        "slug": ("name",),
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
                    "name",
                    "slug",
                    "category",
                    "icon",
                    "description",
                    "is_active",
                    "sort_order",
                )
            },
        ),
        (
            _("Component code"),
            {
                "fields": (
                    "code",
                )
            },
        ),
        (
            _("Related latest articles modules"),
            {
                "fields": ("latest_articles_modules",),
                "description": _(
                    "Used by the Latest blog articles component to offer configured article selections in the template editor."
                ),
            },
        ),
        (
            _("Related tag modules"),
            {
                "fields": ("tag_modules",),
                "description": _(
                    "Used by the Tags component to offer configured tag selections in the template editor."
                ),
            },
        ),
        (
            _("Related image modules"),
            {
                "fields": ("image_modules",),
                "description": _(
                    "Used by the Images component to offer configured image folders in the template editor."
                ),
            },
        ),
        (
            _("AI conversion"),
            {
                "fields": (
                    "ai_conversion_prompt",
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

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        allowed_related_fieldset = None
        if obj is not None and obj.slug == "latest-blog-articles":
            allowed_related_fieldset = _("Related latest articles modules")
        elif obj is not None and obj.slug == "tags-cloud":
            allowed_related_fieldset = _("Related tag modules")
        elif obj is not None and obj.slug == "images":
            allowed_related_fieldset = _("Related image modules")

        return tuple(
            fieldset
            for fieldset in fieldsets
            if (
                fieldset[0] not in (
                    _("Related latest articles modules"),
                    _("Related tag modules"),
                    _("Related image modules"),
                )
                or fieldset[0] == allowed_related_fieldset
            )
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_model_perms(self, request):
        perms = super().get_model_perms(request)
        perms["add"] = False
        perms["delete"] = False
        return perms


@admin.register(Theme)
class ThemeAdmin(ModelAdmin):
    change_list_template = "admin/theme_manager/theme/change_list.html"

    list_display = (
        "name",
        "slug",
        "preview",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "is_active",
    )
    search_fields = (
        "name",
        "slug",
        "description",
    )
    prepopulated_fields = {
        "slug": ("name",),
    }
    readonly_fields = (
        "templates_map_links",
        "created_at",
        "updated_at",
    )
    # inlines = [
    #     ThemeTemplateInline,
    # ]

    def has_add_permission(self, request):
        return False

    fieldsets = (
        (
            _("General"),
            {
                "fields": (
                    "name",
                    "slug",
                    "description",
                    "preview_image",
                    "is_active",
                    # "templates_map",
                )
            },
        ),
        (
            _("HTML files"),
            {
                "fields": (
                    "templates_map_links",
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

    def preview(self, obj):
        if not obj.preview_image:
            return "-"

        return format_html(
            '<img src="{}" style="max-width: 180px; border-radius: 12px;" />',
            obj.preview_image.url,
        )

    preview.short_description = _("Preview")

    def templates_map_links(self, obj):
        if not obj.pk or not obj.templates_map:
            return "-"

        rows = []

        for key, file_path in obj.templates_map.items():
            url = reverse(
                "admin:theme_manager_theme_template_file",
                args=[obj.pk, key],
            )

            rows.append((
                file_path,
                url,
            ))

        return format_html_join(
            mark_safe("<br>"),
            '<a href="{}" target="_blank">/static/{}</a>',
            ((url, file_path) for file_path, url in rows),
        )

    templates_map_links.short_description = _("Theme HTML files")

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "<int:theme_id>/template-file/<str:file_key>/",
                self.admin_site.admin_view(self.template_file_view),
                name="theme_manager_theme_template_file",
            ),
            path(
                "refresh-templates/",
                self.admin_site.admin_view(self.refresh_templates_view),
                name="theme_manager_theme_refresh_templates",
            ),
            path(
                "upload-html-template/",
                self.admin_site.admin_view(self.upload_html_template_view),
                name="theme_manager_theme_upload_html_template",
            ),
        ]

        return custom_urls + urls

    def template_file_view(self, request, theme_id, file_key):
        theme = self.get_object(request, theme_id)

        if not theme:
            raise Http404

        file_path = theme.templates_map.get(file_key)

        if not file_path:
            raise Http404

        real_path = finders.find(file_path)

        if not real_path:
            raise Http404(f"File not found: {file_path}")

        code = Path(real_path).read_text(encoding="utf-8")

        context = {
            **self.admin_site.each_context(request),
            "title": f"{theme.name} / {file_key}",
            "theme": theme,
            "file_key": file_key,
            "file_path": file_path,
            "code": code,
        }

        return render(
            request,
            "theme_manager/template_file_view.html",
            context,
        )

    def refresh_templates_view(self, request):
        static_themes_dir = Path(settings.BASE_DIR) / "static" / "themes"
        django_templates_dir = Path(settings.BASE_DIR) / "templates"

        created_themes = 0
        updated_themes = 0
        created_templates = 0
        updated_templates = 0

        if not static_themes_dir.exists():
            messages.error(request, _("Static themes directory not found."))
            return redirect("admin:theme_manager_theme_changelist")

        for theme_dir in sorted(static_themes_dir.iterdir()):
            if not theme_dir.is_dir():
                continue

            theme_slug = theme_dir.name.lower()
            theme_name = theme_dir.name.replace("-", " ").replace("_", " ").title()

            theme, theme_created = Theme.objects.get_or_create(
                slug=theme_slug,
                defaults={
                    "name": theme_name,
                    "description": "",
                    "is_active": False,
                },
            )

            if theme_created:
                created_themes += 1
            else:
                updated_themes += 1

            templates_map = {}

            for html_file in sorted(theme_dir.rglob("*.html")):
                # Пропускаємо source-файли теми, які ще містять @@include(...)
                content = html_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

                if "@@include" in content:
                    continue

                # Пропускаємо partials типу _head.html, _navigation.html
                if html_file.name.startswith("_"):
                    continue

                key = html_file.stem.lower()

                relative_path = html_file.relative_to(
                    Path(settings.BASE_DIR) / "static"
                )

                templates_map[key] = relative_path.as_posix()

            theme.templates_map = templates_map
            theme.save(update_fields=["templates_map", "updated_at"])

            theme_template_dir = django_templates_dir / theme_slug

            if not theme_template_dir.exists():
                continue

            for django_html_file in sorted(theme_template_dir.rglob("*.html")):
                template_slug = django_html_file.stem.lower()
                template_name = django_html_file.stem.replace("-", " ").replace("_", " ").title()

                template_obj, template_created = ThemeTemplate.objects.get_or_create(
                    theme=theme,
                    slug=template_slug,
                    defaults={
                        "name": template_name,
                        "template_type": TemplateType.PARENT_PAGE,
                        "is_active": True,
                    },
                )

                if template_created:
                    created_templates += 1
                else:
                    template_obj.name = template_name
                    template_obj.save(update_fields=["name", "updated_at"])
                    updated_templates += 1

        messages.success(
            request,
            (
                _(
                    "Templates refreshed. Created themes: %(created_themes)s. "
                    "Updated themes: %(updated_themes)s. "
                    "Created templates: %(created_templates)s. "
                    "Updated templates: %(updated_templates)s."
                )
                % {
                    "created_themes": created_themes,
                    "updated_themes": updated_themes,
                    "created_templates": created_templates,
                    "updated_templates": updated_templates,
                }
            ),
        )

        return redirect("admin:theme_manager_theme_changelist")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        extra_context["refresh_templates_url"] = reverse(
            "admin:theme_manager_theme_refresh_templates"
        )

        extra_context["upload_html_template_url"] = reverse(
            "admin:theme_manager_theme_upload_html_template"
        )

        return super().changelist_view(request, extra_context=extra_context)

    def upload_html_template_view(self, request):
        if request.method == "POST":
            form = ThemeZipUploadForm(request.POST, request.FILES)

            if form.is_valid():
                zip_file = form.cleaned_data["zip_file"]

                upload_dir = Path(settings.BASE_DIR) / "tmp" / "theme_uploads"
                upload_dir.mkdir(parents=True, exist_ok=True)

                fs = FileSystemStorage(location=upload_dir)
                filename = fs.save(zip_file.name, zip_file)
                zip_path = upload_dir / filename

                extract_dir = upload_dir / zip_path.stem

                if extract_dir.exists():
                    shutil.rmtree(extract_dir)

                extract_dir.mkdir(parents=True, exist_ok=True)

                try:
                    with zipfile.ZipFile(zip_path, "r") as archive:
                        for member in archive.namelist():
                            member_path = Path(member)

                            if member_path.is_absolute() or ".." in member_path.parts:
                                raise ValueError("Unsafe ZIP archive.")

                        archive.extractall(extract_dir)

                    root_items = [
                        item for item in extract_dir.iterdir()
                        if item.is_dir()
                    ]

                    if len(root_items) != 1:
                        messages.error(
                            request,
                            _("ZIP archive must contain exactly one root folder.")
                        )
                        return redirect("admin:theme_manager_theme_upload_html_template")

                    source_theme_dir = root_items[0]

                    theme_slug = slugify(source_theme_dir.name)
                    theme_name = source_theme_dir.name.replace("-", " ").replace("_", " ").title()

                    if not theme_slug:
                        messages.error(request, _("Invalid theme folder name."))
                        return redirect("admin:theme_manager_theme_upload_html_template")

                    static_theme_dir = (
                            Path(settings.BASE_DIR) / "static" / "themes" / theme_slug
                    )

                    templates_theme_dir = (
                            Path(settings.BASE_DIR) / "templates" / theme_slug
                    )

                    if static_theme_dir.exists():
                        shutil.rmtree(static_theme_dir)

                    static_theme_dir.mkdir(parents=True, exist_ok=True)
                    templates_theme_dir.mkdir(parents=True, exist_ok=True)

                    for item in source_theme_dir.iterdir():
                        target = static_theme_dir / item.name

                        if item.is_dir():
                            shutil.copytree(item, target)
                        else:
                            shutil.copy2(item, target)

                    templates_map = {}

                    for html_file in sorted(static_theme_dir.rglob("*.html")):
                        content = html_file.read_text(
                            encoding="utf-8",
                            errors="ignore",
                        )

                        if "@@include" in content:
                            continue

                        if html_file.name.startswith("_"):
                            continue

                        key = html_file.stem.lower()

                        relative_path = html_file.relative_to(
                            Path(settings.BASE_DIR) / "static"
                        )

                        templates_map[key] = relative_path.as_posix()

                    theme, created = Theme.objects.get_or_create(
                        slug=theme_slug,
                        defaults={
                            "name": theme_name,
                            "description": "",
                            "is_active": False,
                        },
                    )

                    theme.name = theme_name
                    theme.templates_map = templates_map
                    theme.save(update_fields=["name", "templates_map", "updated_at"])

                    messages.success(
                        request,
                        _(
                            "Theme '%(theme)s' uploaded successfully. "
                            "HTML files found: %(count)s."
                        )
                        % {"theme": theme.name, "count": len(templates_map)}
                    )

                    return redirect("admin:theme_manager_theme_change", theme.pk)

                except zipfile.BadZipFile:
                    messages.error(request, _("Invalid ZIP archive."))

                except Exception as error:
                    messages.error(
                        request,
                        _("Upload failed: %(error)s") % {"error": error},
                    )

                finally:
                    if zip_path.exists():
                        zip_path.unlink()

                    if extract_dir.exists():
                        shutil.rmtree(extract_dir)

        else:
            form = ThemeZipUploadForm()

        context = {
            **self.admin_site.each_context(request),
            "title": _("Upload HTML template"),
            "form": form,
            "opts": self.model._meta,
        }

        return render(
            request,
            "admin/theme_manager/theme/upload_html_template.html",
            context,
        )


class TemplateHtmlCodeWidget(forms.Textarea):
    class Media:
        css = {
            "all": (
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/fold/foldgutter.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/hint/show-hint.min.css",
                "theme_manager/css/main.css",
                "admin/css/cms-link-browser.css",
                "theme_manager/css/template-html-code-layout.css",
            )
        }

        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/xml/xml.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/fold/foldcode.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/fold/foldgutter.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/fold/xml-fold.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/closebrackets.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/closetag.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/matchtags.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/selection/active-line.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/selection/mark-selection.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/hint/show-hint.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/hint/xml-hint.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/hint/html-hint.min.js",
            "admin/js/cms-link-browser.js",
            "theme_manager/js/template-html-code.js",
        )


class ArticleExtraFieldsSchemaWidget(forms.Textarea):
    def format_value(self, value):
        if value in (None, ""):
            return ""

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return value

        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)

        return super().format_value(value)

    class Media:
        css = {
            "all": (
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css",
                "theme_manager/css/main.css",
            )
        }

        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/matchbrackets.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/closebrackets.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/selection/active-line.min.js",
            "theme_manager/js/article-extra-fields-schema.js",
        )


class ThemeTemplateAdminForm(forms.ModelForm):
    ARTICLE_EXTRA_FIELD_TYPES = {
        "text",
        "textarea",
        "email",
        "number",
        "password",
        "url",
        "tel",
        "search",
        "date",
        "datetime-local",
        "time",
        "month",
        "week",
        "color",
        "file",
        "checkbox",
        "radio",
        "select",
        "multiselect",
        "hidden",
    }

    page_title_en = forms.CharField(
        label=_("Page title [en]"),
        max_length=255,
        required=False,
        widget=UnfoldAdminTextInputWidget(attrs={
            "class": "mt mt-field-page_title-en mt-default",
        }),
    )
    page_title_uk = forms.CharField(
        label=_("Page title [uk]"),
        max_length=255,
        required=False,
        widget=UnfoldAdminTextInputWidget(attrs={
            "class": "mt mt-field-page_title-uk",
        }),
    )
    page_slug = forms.SlugField(
        label=_("Page slug"),
        max_length=250,
        required=False,
        widget=UnfoldAdminTextInputWidget(),
    )
    page_description_en = forms.CharField(
        label=_("Page description [en]"),
        required=False,
        widget=UnfoldAdminTextareaWidget(attrs={
            "class": "mt mt-field-page_description-en mt-default",
            "rows": 4,
        }),
    )
    page_description_uk = forms.CharField(
        label=_("Page description [uk]"),
        required=False,
        widget=UnfoldAdminTextareaWidget(attrs={
            "class": "mt mt-field-page_description-uk",
            "rows": 4,
        }),
    )
    page_keywords = forms.CharField(
        label=_("Page keywords"),
        max_length=255,
        required=False,
        help_text=_("Comma-separated keywords."),
        widget=UnfoldAdminTextInputWidget(),
    )
    page_preview_image = forms.ImageField(
        label=_("Page preview image"),
        required=False,
        help_text=SOCIAL_PREVIEW_SPEC.help_text,
        widget=UnfoldAdminImageFieldWidget(),
    )
    page_og_type = forms.CharField(
        label=_("Page OG type"),
        max_length=100,
        required=False,
        widget=UnfoldAdminTextInputWidget(),
    )
    page_schema_graph = forms.JSONField(
        label=_("Page schema graph"),
        required=False,
        initial=dict,
        help_text=_("Optional JSON-LD graph for this page."),
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 6}),
    )
    page_is_published = forms.BooleanField(
        label=_("Page published"),
        required=False,
        initial=True,
        widget=UnfoldBooleanSwitchWidget(),
    )
    page_noindex = forms.BooleanField(
        label=_("Page noindex"),
        required=False,
        widget=UnfoldBooleanSwitchWidget(),
    )
    article_extra_fields_schema = forms.JSONField(
        label=_("Article extra fields schema"),
        required=False,
        initial=dict,
        help_text=mark_safe(
            _(
                "JSON schema for extra article fields used by categories with this article template."
            )
            + """
            <br>
            <small>
                Example:
                <pre style="margin-top: 4px; font-size: 12px; line-height: 1.4;">{
  "name_value": {
    "label": "Difficulty",
    "type": "select",
    "required": false,
    "choices": ["Beginner", "Intermediate", "Advanced"],
    "default": ""
  }
}</pre>
                The object key, for example <code>name_value</code>, is the variable slug.
                Recommended keys: <code>label</code>, <code>type</code>,
                <code>required</code>, <code>default</code>, <code>placeholder</code>,
                <code>help_text</code>, <code>choices</code>.
                Type values: <code>text</code>, <code>textarea</code>, <code>email</code>,
                <code>number</code>, <code>password</code>, <code>url</code>, <code>tel</code>,
                <code>search</code>, <code>date</code>, <code>datetime-local</code>,
                <code>time</code>, <code>month</code>, <code>week</code>, <code>color</code>,
                <code>file</code>, <code>checkbox</code>, <code>radio</code>,
                <code>select</code>, <code>multiselect</code>, <code>hidden</code>.
            </small>
            """
        ),
        widget=ArticleExtraFieldsSchemaWidget(
            attrs={
                "class": "codemirror-article-extra-fields-schema",
                "rows": 8,
            }
        ),
    )
    template_html_code = forms.CharField(
        label=_("Template HTML code"),
        required=False,
        widget=TemplateHtmlCodeWidget(
            attrs={
                "class": "codemirror-template-html",
                "rows": 35,
                "style": "font-family: monospace;",
            }
        ),
    )

    class Meta:
        model = ThemeTemplate
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        obj = self.instance
        code = ""
        widget_attrs = self.fields["template_html_code"].widget.attrs
        page = None
        self.fields["theme"].disabled = True

        if not obj or not obj.pk:
            default_theme = Theme.get_active() or Theme.objects.order_by("name").first()

            if default_theme:
                self.fields["theme"].initial = default_theme
                self.initial["theme"] = default_theme

        if obj and obj.pk:
            page = Page.objects.filter(template=obj).first()

        if page and not self.is_bound:
            self.initial.update({
                "page_title_en": page.title_en or "",
                "page_title_uk": page.title_uk or "",
                "page_slug": page.slug,
                "page_description_en": page.description_en or "",
                "page_description_uk": page.description_uk or "",
                "page_keywords": page.keywords,
                "page_preview_image": page.preview_image,
                "page_og_type": page.og_type,
                "page_schema_graph": page.schema_graph,
                "page_is_published": page.is_published,
                "page_noindex": page.noindex,
            })

        widget_attrs["data-source-file-code-url"] = reverse(
            "admin:theme_manager_themetemplate_source_file_code"
        )
        widget_attrs["data-asset-browser-url"] = reverse(
            "admin:theme_manager_themetemplate_asset_browser"
        )
        widget_attrs["data-template-components-url"] = reverse(
            "admin:theme_manager_themetemplate_components"
        )
        widget_attrs["data-cms-link-options-url"] = reverse(
            "admin:theme_manager_themetemplate_cms_link_options"
        )
        widget_attrs["data-blog-category-tree-url"] = reverse(
            "admin:theme_manager_themetemplate_blog_category_tree"
        )
        widget_attrs["data-theme-html-files"] = json.dumps(
            {
                str(theme.pk): ThemeTemplateAdmin.get_theme_html_files_for_theme(theme)
                for theme in Theme.objects.order_by("name")
            }
        )
        widget_attrs["data-theme-include-blocks"] = json.dumps(
            {
                str(theme.pk): ThemeTemplateAdmin.get_include_blocks_for_theme(theme)
                for theme in Theme.objects.order_by("name")
            }
        )
        widget_attrs["data-theme-base-templates"] = json.dumps(
            {
                str(theme.pk): ThemeTemplateAdmin.get_base_templates_for_theme(theme)
                for theme in Theme.objects.order_by("name")
            }
        )
        widget_attrs["data-theme-slugs"] = json.dumps(
            {
                str(theme.pk): theme.slug
                for theme in Theme.objects.order_by("name")
            }
        )
        if obj and obj.pk and obj.theme_id and obj.slug:
            widget_attrs["data-theme-id"] = str(obj.theme_id)
            file_path = ThemeTemplateAdmin.get_template_file_path(obj)

            if file_path.exists():
                code = ThemeTemplateAdmin.read_template_code(file_path)

            widget_attrs["data-file-code-url"] = reverse(
                "admin:theme_manager_themetemplate_change_file_code",
                args=[obj.pk],
            )
            widget_attrs["data-convert-static-url"] = reverse(
                "admin:theme_manager_themetemplate_change_convert_static",
                args=[obj.pk],
            )
            widget_attrs["data-analyze-loads-url"] = reverse(
                "admin:theme_manager_themetemplate_change_analyze_loads",
                args=[obj.pk],
            )
            widget_attrs["data-ai-transform-url"] = reverse(
                "admin:theme_manager_themetemplate_change_ai_transform",
                args=[obj.pk],
            )
            widget_attrs["data-extract-include-url"] = reverse(
                "admin:theme_manager_themetemplate_change_extract_include",
                args=[obj.pk],
            )
            widget_attrs["data-extract-page-block-url"] = reverse(
                "admin:theme_manager_themetemplate_change_extract_page_block",
                args=[obj.pk],
            )
            widget_attrs["data-history-url"] = reverse(
                "admin:theme_manager_themetemplate_change_history",
                args=[obj.pk],
            )
            widget_attrs["data-history-compare-url"] = reverse(
                "admin:theme_manager_themetemplate_change_history_compare",
                args=[obj.pk],
            )
            widget_attrs["data-history-restore-url"] = reverse(
                "admin:theme_manager_themetemplate_change_history_restore",
                args=[obj.pk],
            )
            widget_attrs["data-format-url"] = reverse(
                "admin:theme_manager_themetemplate_change_format",
                args=[obj.pk],
            )
            widget_attrs["data-html-files"] = json.dumps(
                ThemeTemplateAdmin.get_theme_html_files_for_theme(obj.theme)
            )

        self.fields["template_html_code"].initial = code

    def clean_article_extra_fields_schema(self):
        schema = self.cleaned_data.get("article_extra_fields_schema") or {}

        if not isinstance(schema, dict):
            raise forms.ValidationError(_("Schema must be a JSON object."))

        variable_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

        for field_name, config in schema.items():
            if not isinstance(field_name, str) or not variable_pattern.match(field_name):
                raise forms.ValidationError(
                    _(
                        "Each field key must be a valid variable slug, for example name_value."
                    )
                )

            if not isinstance(config, dict):
                raise forms.ValidationError(
                    _("Field '%(field)s' must contain a JSON object."),
                    params={"field": field_name},
                )

            label = config.get("label")
            if not isinstance(label, str) or not label.strip():
                raise forms.ValidationError(
                    _("Field '%(field)s' must have a non-empty label."),
                    params={"field": field_name},
                )

            field_type = config.get("type")
            if field_type not in self.ARTICLE_EXTRA_FIELD_TYPES:
                raise forms.ValidationError(
                    _("Field '%(field)s' has invalid type '%(type)s'."),
                    params={
                        "field": field_name,
                        "type": field_type,
                    },
                )

            choices = config.get("choices")
            if field_type in {"select", "multiselect", "radio"}:
                if not isinstance(choices, list) or not choices:
                    raise forms.ValidationError(
                        _("Field '%(field)s' must define a non-empty choices list."),
                        params={"field": field_name},
                    )

                if any(
                    not isinstance(choice, str) or not choice.strip()
                    for choice in choices
                ):
                    raise forms.ValidationError(
                        _("Field '%(field)s' choices must be non-empty strings."),
                        params={"field": field_name},
                    )
            elif field_type == "checkbox" and choices not in (None, ""):
                if not isinstance(choices, list) or not choices:
                    raise forms.ValidationError(
                        _("Field '%(field)s' choices must be a non-empty list."),
                        params={"field": field_name},
                    )

                if any(
                    not isinstance(choice, str) or not choice.strip()
                    for choice in choices
                ):
                    raise forms.ValidationError(
                        _("Field '%(field)s' choices must be non-empty strings."),
                        params={"field": field_name},
                    )
            elif choices not in (None, ""):
                raise forms.ValidationError(
                    _(
                        "Field '%(field)s' can use choices only with select, multiselect, radio, or checkbox."
                    ),
                    params={"field": field_name},
                )

            required = config.get("required")
            if required is not None and not isinstance(required, bool):
                raise forms.ValidationError(
                    _("Field '%(field)s' required must be true or false."),
                    params={"field": field_name},
                )

            for text_key in ("default", "placeholder", "help_text"):
                value = config.get(text_key)
                if value is not None and not isinstance(value, str):
                    raise forms.ValidationError(
                        _("Field '%(field)s' %(key)s must be a string."),
                        params={
                            "field": field_name,
                            "key": text_key,
                        },
                    )

        return schema

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("template_type") != TemplateType.PARENT_PAGE:
            if self.instance and self.instance.pk:
                if Page.objects.filter(template=self.instance).exists():
                    self.add_error(
                        "template_type",
                        _(
                            "This template is linked to a page and must remain a Parent Page."
                        ),
                    )

            return cleaned_data

        required_fields = (
            "page_title_en",
            "page_slug",
            "page_description_en",
        )

        for field_name in required_fields:
            if not cleaned_data.get(field_name):
                self.add_error(field_name, _("This field is required for Parent Page templates."))

        slug = cleaned_data.get("page_slug")

        if slug:
            existing_page = Page.objects.filter(slug=slug)

            if self.instance and self.instance.pk:
                existing_page = existing_page.exclude(template=self.instance)

            if existing_page.exists():
                self.add_error("page_slug", _("A page with this slug already exists."))

        if "page_preview_image" in self.changed_data:
            preview_image = cleaned_data.get("page_preview_image")

            if preview_image:
                try:
                    cleaned_data["page_preview_image"] = process_uploaded_image(
                        preview_image,
                        SOCIAL_PREVIEW_SPEC,
                    )
                except forms.ValidationError as error:
                    self.add_error("page_preview_image", error)

        return cleaned_data

    def save_page(self):
        template = self.instance

        if template.template_type != TemplateType.PARENT_PAGE:
            return None

        page = Page.objects.filter(template=template).first() or Page(template=template)
        title_en = self.cleaned_data["page_title_en"]
        description_en = self.cleaned_data["page_description_en"]

        page.title = title_en
        page.title_en = title_en
        page.title_uk = self.cleaned_data.get("page_title_uk", "")
        page.slug = self.cleaned_data["page_slug"]
        page.description = description_en
        page.description_en = description_en
        page.description_uk = self.cleaned_data.get("page_description_uk", "")
        page.keywords = self.cleaned_data.get("page_keywords", "")
        page.og_type = self.cleaned_data.get("page_og_type", "")
        page.schema_graph = self.cleaned_data.get("page_schema_graph") or {}
        page.is_published = self.cleaned_data.get("page_is_published", False)
        page.noindex = self.cleaned_data.get("page_noindex", False)

        if "page_preview_image" in self.changed_data:
            preview_image = self.cleaned_data.get("page_preview_image")

            if preview_image:
                page.preview_image = preview_image
            else:
                page.preview_image = None

        page.template = template
        page.save()
        return page


@admin.register(ThemeTemplate)
class ThemeTemplateAdmin(ModelAdmin):
    form = ThemeTemplateAdminForm
    save_as = True

    class Media:
        js = (
            *TabbedTranslationAdmin.Media.js,
            "theme_manager/js/theme-template-page-fields.js",
        )
        css = TabbedTranslationAdmin.Media.css

    list_display = (
        "structured_name",
        "theme",
        "template_type",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "theme",
        "template_type",
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
    )

    @admin.display(description=_("Name"))
    def structured_name(self, obj):
        child_types = {
            TemplateType.INCLUDE_BLOCK,
            TemplateType.PARENT_PAGE,
            TemplateType.PARENT_BLOG,
            TemplateType.PARENT_ARTICLE,
            TemplateType.SEARCH_PAGE,
        }

        if obj.template_type in child_types:
            return f"-- {obj.name}"

        return obj.name

    def get_ordering(self, request):
        type_order = [value for value, _label in TemplateType.choices]
        type_rank = Case(
            *[
                When(template_type=value, then=Value(position))
                for position, value in enumerate(type_order)
            ],
            default=Value(len(type_order)),
            output_field=IntegerField(),
        )

        return ("theme__name", type_rank, "name", "pk")

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(
            request,
            queryset,
            search_term,
        )
        source = (
            request.GET.get("app_label"),
            request.GET.get("model_name"),
            request.GET.get("field_name"),
        )
        template_type_by_source = {
            ("blog_manager", "blogsettings", "default_category_template"): TemplateType.PARENT_BLOG,
            ("blog_manager", "blogsettings", "default_paginated_category_template"): TemplateType.PARENT_BLOG,
            ("blog_manager", "blogsettings", "default_article_template"): TemplateType.PARENT_ARTICLE,
            ("blog_manager", "category", "theme_template"): TemplateType.PARENT_BLOG,
            ("blog_manager", "category", "paginated_theme_template"): TemplateType.PARENT_BLOG,
            ("blog_manager", "category", "article_theme_template"): TemplateType.PARENT_ARTICLE,
            ("blog_manager", "article", "theme_template"): TemplateType.PARENT_ARTICLE,
        }
        template_type = template_type_by_source.get(source)

        if template_type:
            queryset = queryset.filter(
                template_type=template_type,
                theme__is_active=True,
                is_active=True,
            )

        return queryset, use_distinct

    prepopulated_fields = {
        "slug": ("name",),
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
                    "theme",
                    "template_type",
                    "name",
                    "slug",
                    "is_active",
                )
            },
        ),
        (
            _("Page"),
            {
                "classes": ("theme-template-page-fields",),
                "fields": (
                    "page_title_en",
                    "page_title_uk",
                    "page_slug",
                    "page_description_en",
                    "page_description_uk",
                    "page_keywords",
                    "page_preview_image",
                    "page_og_type",
                    "page_schema_graph",
                    "page_is_published",
                    "page_noindex",
                ),
            },
        ),
        (
            _("Article"),
            {
                "classes": ("theme-template-article-fields",),
                "fields": (
                    "article_extra_fields_schema",
                ),
            },
        ),
        (
            _("Template HTML code"),
            {
                "fields": (
                    "template_html_code",
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

    def edit_template_button(self, obj):
        if not obj or not obj.pk:
            url = reverse("admin:theme_manager_themetemplate_add")

            return format_html(
                '''
                <a href="{}"
                   target="_blank"
                   style="
                    display:block;
                    width:100%;
                    text-align:center;
                    padding:10px 18px;
                    background:#2563eb;
                    color:#fff;
                    border-radius:8px;
                    font-size:14px;
                    font-weight:600;
                    text-decoration:none;
                    box-sizing:border-box;
                   ">
                   Open empty HTML editor
                </a>
                ''',
                url,
            )

        url = reverse(
            "admin:theme_manager_themetemplate_change",
            args=[obj.pk],
        )

        return format_html(
            '''
            <a href="{}"
               target="_blank"
               style="
                    display:block;
                    width:100%;
                    text-align:center;
                    padding:10px 18px;
                    background:#2563eb;
                    color:#fff;
                    border-radius:8px;
                    font-size:14px;
                    font-weight:600;
                    text-decoration:none;
                    box-sizing:border-box;
               ">
               ✏️ Edit template
            </a>
            ''',
            url,
        )

    edit_template_button.short_description = _("Template editor")

    @staticmethod
    def get_template_file_path(template):
        return (
            Path(settings.BASE_DIR)
            / "templates"
            / template.theme.slug
            / f"{template.slug}.html"
        )

    @staticmethod
    def normalize_template_code(code):
        if code is None:
            return ""

        return (
            code
            .replace("\r\r\n", "\n")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )

    @classmethod
    def read_template_code(cls, file_path):
        return cls.normalize_template_code(
            file_path.read_bytes().decode("utf-8")
        )

    @classmethod
    def write_template_code(cls, file_path, code):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            cls.normalize_template_code(code),
            encoding="utf-8",
            newline="\n",
        )

    @staticmethod
    def get_theme_html_files_for_theme(theme):
        if not theme:
            return []

        return [
            {
                "key": key,
                "name": file_path,
                "path": file_path,
            }
            for key, file_path in theme.templates_map.items()
        ]

    @staticmethod
    def get_include_blocks_for_theme(theme):
        if not theme:
            return []

        return [
            {
                "name": template.name,
                "slug": template.slug,
                "include": "{% include '" + theme.slug + "/" + template.slug + ".html' %}",
            }
            for template in ThemeTemplate.objects.filter(
                theme=theme,
                template_type=TemplateType.INCLUDE_BLOCK,
                is_active=True,
            ).order_by("name", "slug")
        ]

    @staticmethod
    def get_base_templates_for_theme(theme):
        if not theme:
            return []

        return [
            {
                "name": template.name,
                "slug": template.slug,
                "extends": "{% extends '" + theme.slug + "/" + template.slug + ".html' %}",
            }
            for template in ThemeTemplate.objects.filter(
                theme=theme,
                template_type=TemplateType.BASE_TEMPLATE,
                is_active=True,
            ).order_by("name", "slug")
        ]

    def get_theme_html_files(self, theme):
        return self.get_theme_html_files_for_theme(theme)

    @staticmethod
    def format_code_before_save(code):
        return format_template_code(code or "")

    @classmethod
    def build_unique_slug(cls, theme_id, base_slug, preferred_suffix=None):
        slug_field = ThemeTemplate._meta.get_field("slug")
        max_length = slug_field.max_length
        normalized_slug = slugify(unidecode(base_slug or "")) or "template"
        suffix = str(preferred_suffix or "copy")

        def with_suffix(current_suffix):
            candidate_suffix = f"-{current_suffix}"
            return f"{normalized_slug[:max_length - len(candidate_suffix)]}{candidate_suffix}"

        candidate = with_suffix(suffix)
        counter = 2

        while ThemeTemplate.objects.filter(
            theme_id=theme_id,
            slug=candidate,
        ).exists():
            candidate = with_suffix(f"{suffix}-{counter}")
            counter += 1

        return candidate

    def get_save_as_new_post_data(self, request, object_id=None):
        post_data = request.POST.copy()
        theme_id = post_data.get("theme")
        base_slug = post_data.get("slug")

        if theme_id and base_slug:
            post_data["slug"] = self.build_unique_slug(
                theme_id=theme_id,
                base_slug=base_slug,
                preferred_suffix=object_id,
            )

        return post_data

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method == "POST" and "_saveasnew" in request.POST:
            request.POST = self.get_save_as_new_post_data(
                request,
                object_id=object_id,
            )

        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context,
        )

    def move_template_file_for_slug_change(self, request, old_template, new_template):
        if not old_template or not new_template.pk:
            return

        old_file_path = self.get_template_file_path(old_template)
        new_file_path = self.get_template_file_path(new_template)

        if old_file_path == new_file_path or not old_file_path.exists():
            return

        new_file_path.parent.mkdir(parents=True, exist_ok=True)

        if new_file_path.exists():
            messages.warning(
                request,
                _(
                    "Template slug was changed, but the target HTML file already "
                    "exists. The old file was kept to avoid overwriting it."
                ),
            )
            return

        old_file_path.rename(new_file_path)

    def save_model(self, request, obj, form, change):
        old_template = None

        if change and "_saveasnew" not in request.POST:
            old_template = ThemeTemplate.objects.filter(pk=obj.pk).first()

        super().save_model(request, obj, form, change)
        self.move_template_file_for_slug_change(request, old_template, obj)

        if hasattr(form, "save_page"):
            form.save_page()

        code = form.cleaned_data.get("template_html_code")

        if code is None:
            return

        template_file_path = self.get_template_file_path(obj)
        save_template_code(
            template=obj,
            file_path=template_file_path,
            code=self.format_code_before_save(code),
            user=request.user,
            source="admin_save",
        )
        css_classes = []
        if obj.template_type == TemplateType.PARENT_ARTICLE:
            css_classes = collect_template_css_classes(template_file_path)
        ThemeTemplate.objects.filter(pk=obj.pk).update(css_classes=css_classes)
        obj.css_classes = css_classes

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "change-tools/source-file-code/",
                self.admin_site.admin_view(self.template_source_file_code_view),
                name="theme_manager_themetemplate_source_file_code",
            ),
            path(
                "change-tools/assets/",
                self.admin_site.admin_view(self.template_editor_asset_browser_view),
                name="theme_manager_themetemplate_asset_browser",
            ),
            path(
                "change-tools/components/",
                self.admin_site.admin_view(self.template_editor_components_view),
                name="theme_manager_themetemplate_components",
            ),
            path(
                "change-tools/cms-link-options/",
                self.admin_site.admin_view(self.template_editor_cms_link_options_view),
                name="theme_manager_themetemplate_cms_link_options",
            ),
            path(
                "change-tools/blog-category-tree/",
                self.admin_site.admin_view(self.template_editor_blog_category_tree_view),
                name="theme_manager_themetemplate_blog_category_tree",
            ),
            path(
                "<int:template_id>/change-tools/file-code/",
                self.admin_site.admin_view(self.template_editor_file_code_view),
                name="theme_manager_themetemplate_change_file_code",
            ),
            path(
                "<int:template_id>/change-tools/convert-static/",
                self.admin_site.admin_view(self.template_editor_convert_static_view),
                name="theme_manager_themetemplate_change_convert_static",
            ),
            path(
                "<int:template_id>/change-tools/analyze-loads/",
                self.admin_site.admin_view(self.template_editor_analyze_loads_view),
                name="theme_manager_themetemplate_change_analyze_loads",
            ),
            path(
                "<int:template_id>/change-tools/ai-transform/",
                self.admin_site.admin_view(self.template_editor_ai_transform_view),
                name="theme_manager_themetemplate_change_ai_transform",
            ),
            path(
                "<int:template_id>/change-tools/extract-include/",
                self.admin_site.admin_view(self.template_editor_extract_include_view),
                name="theme_manager_themetemplate_change_extract_include",
            ),
            path(
                "<int:template_id>/change-tools/extract-page-block/",
                self.admin_site.admin_view(self.template_editor_extract_page_block_view),
                name="theme_manager_themetemplate_change_extract_page_block",
            ),
            path(
                "<int:template_id>/change-tools/history/",
                self.admin_site.admin_view(self.template_editor_history_view),
                name="theme_manager_themetemplate_change_history",
            ),
            path(
                "<int:template_id>/change-tools/history/compare/",
                self.admin_site.admin_view(self.template_editor_history_compare_view),
                name="theme_manager_themetemplate_change_history_compare",
            ),
            path(
                "<int:template_id>/change-tools/history/restore/",
                self.admin_site.admin_view(self.template_editor_history_restore_view),
                name="theme_manager_themetemplate_change_history_restore",
            ),
            path(
                "<int:template_id>/change-tools/format/",
                self.admin_site.admin_view(self.template_editor_format_view),
                name="theme_manager_themetemplate_change_format",
            ),
        ]

        return custom_urls + urls

    def template_source_file_code_view(self, request):
        theme = Theme.objects.filter(pk=request.GET.get("theme_id")).first()
        file_key = request.GET.get("file")

        if not theme or not file_key:
            return JsonResponse({"code": ""})

        file_path = theme.templates_map.get(file_key)

        if not file_path:
            return JsonResponse({"code": ""}, status=404)

        real_path = Path(settings.BASE_DIR) / "static" / file_path

        if not real_path.exists():
            return JsonResponse({"code": ""})

        return JsonResponse({
            "code": self.read_template_code(real_path),
            "file": file_path,
            "key": file_key,
        })

    def template_editor_asset_browser_view(self, request):
        if not self.has_change_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)

        if request.method == "POST":
            if request.POST.get("action") == "delete_many" or "assets" in request.POST:
                try:
                    asset_items = json.loads(request.POST.get("assets", "[]"))
                except json.JSONDecodeError:
                    return JsonResponse({"error": "Enter a valid asset list."}, status=400)

                if not isinstance(asset_items, list):
                    return JsonResponse({"error": "Enter a valid asset list."}, status=400)

                deleted, failed = delete_image_assets(asset_items)
                return JsonResponse({
                    "deleted": deleted,
                    "failed": failed,
                    "message": f"Deleted {len(deleted)} image(s).",
                })

            theme = Theme.objects.filter(pk=request.POST.get("theme_id")).first()
            default_static_prefix = ""
            if theme:
                default_static_prefix = f"themes/{theme.slug}/assets/img"

            try:
                asset, replaced = save_uploaded_image(
                    uploaded_file=request.FILES.get("image"),
                    asset_type=request.POST.get("asset_type", ""),
                    target_path=request.POST.get("path", ""),
                    overwrite=request.POST.get("overwrite") == "true",
                    default_static_prefix=default_static_prefix,
                )
            except AssetUploadError as error:
                return JsonResponse({"error": str(error)}, status=400)
            except OSError:
                return JsonResponse(
                    {"error": "The image could not be saved."},
                    status=500,
                )

            return JsonResponse({
                "asset": asset,
                "replaced": replaced,
                "message": (
                    "Image replaced successfully."
                    if replaced
                    else "Image uploaded successfully."
                ),
            })

        if request.method != "GET":
            return JsonResponse({"error": "GET or POST required"}, status=405)

        assets = collect_image_assets()
        return JsonResponse({
            "assets": assets,
            "count": len(assets),
            "static_count": sum(
                1 for asset in assets if asset["type"] == "static"
            ),
            "media_count": sum(
                1 for asset in assets if asset["type"] == "media"
            ),
        })

    def template_editor_components_view(self, request):
        if request.method != "GET":
            return JsonResponse({"error": _("GET required")}, status=405)
        if not self.has_change_permission(request):
            return JsonResponse({"error": _("Permission denied")}, status=403)

        components = []
        queryset = (
            TemplateComponent.objects
            .filter(is_active=True)
            .prefetch_related(
                "latest_articles_modules",
                "tag_modules",
                "image_modules",
            )
            .order_by("category", "sort_order", "name")
        )

        for component in queryset:
            base_data = {
                "name": gettext(component.name),
                "slug": component.slug,
                "category": gettext(component.category),
                "icon": component.icon,
                "description": gettext(component.description),
                "code": component.code,
            }
            modules = list(
                component.latest_articles_modules
                .filter(is_active=True)
                .order_by("name", "pk")
            )

            if component.slug == "latest-blog-articles" and not modules:
                modules = list(
                    LatestArticlesModule.objects
                    .filter(is_active=True)
                    .order_by("name", "pk")
                )

            if component.slug == "tags-cloud":
                modules = list(
                    component.tag_modules
                    .filter(is_active=True)
                    .order_by("name", "pk")
                )
                if not modules:
                    modules = list(
                        TagModule.objects
                        .filter(is_active=True)
                        .order_by("name", "pk")
                    )

            if component.slug == "images":
                modules = list(
                    component.image_modules
                    .filter(is_active=True)
                    .order_by("name", "pk")
                )
                if not modules:
                    modules = list(
                        ImageModule.objects
                        .filter(is_active=True)
                        .order_by("name", "pk")
                    )

            if component.slug not in (
                "latest-blog-articles",
                "tags-cloud",
                "images",
            ):
                components.append(base_data)
                continue

            base_data["modules"] = []
            for module in modules:
                if component.slug == "tags-cloud":
                    module_code = (
                        "{% load blog_modules %}\n"
                        f'{{% tags_module "{module.slug}" as module_tags %}}\n'
                        f"{component.code}"
                    )
                elif component.slug == "images":
                    module_code = (
                        "{% load image_modules %}\n"
                        f'{{% image_module "{module.slug}" as module_images %}}\n'
                        f"{component.code}"
                    )
                else:
                    module_code = (
                        "{% load blog_modules %}\n"
                        f'{{% latest_articles_module "{module.slug}" as latest_blog_articles %}}\n'
                        f"{component.code}"
                    )
                base_data["modules"].append(
                    {
                        "name": module.name,
                        "slug": module.slug,
                        "code": module_code,
                    }
                )
            components.append(base_data)

        return JsonResponse({
            "components": components,
            "count": len(components),
        })

    def template_editor_blog_category_tree_view(self, request):
        if request.method != "GET":
            return JsonResponse({"error": "GET required"}, status=405)
        if not self.has_change_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)

        categories = list(
            Category.objects.order_by(
                "parent_id",
                "sort_order",
                "title",
                "id",
            )
        )
        children_map = {}
        child_counts = {}

        for category in categories:
            children_map.setdefault(category.parent_id, []).append(category)
            child_counts[category.pk] = 0

        for category in categories:
            if category.parent_id:
                child_counts[category.parent_id] = child_counts.get(category.parent_id, 0) + 1

        items = []

        def append_branch(parent_id=None, depth=0):
            for category in children_map.get(parent_id, []):
                items.append({
                    "id": category.pk,
                    "title": category.title,
                    "slug": category.slug,
                    "depth": depth,
                    "child_count": child_counts.get(category.pk, 0),
                    "url_tag": "{% url 'blog:category' category_slug='" + category.slug + "' %}",
                })
                append_branch(category.pk, depth + 1)

        append_branch()

        return JsonResponse({
            "items": items,
            "count": len(items),
        })

    def template_editor_cms_link_options_view(self, request):
        if request.method != "GET":
            return JsonResponse({"error": "GET required"}, status=405)
        if not self.has_change_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)

        content_type = request.GET.get("type", "")
        query = request.GET.get("q", "").strip()
        try:
            page = max(1, int(request.GET.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            payload = get_cms_link_options(
                content_type,
                query=query,
                page=page,
                language=request.GET.get("language"),
            )
        except ValueError:
            return JsonResponse({"error": "Unknown content type"}, status=400)
        return JsonResponse(payload)

    def new_template_editor_file_code_view(self, request):
        return self.template_source_file_code_view(request)

    def new_template_editor_convert_static_view(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        theme = Theme.objects.filter(pk=request.POST.get("theme_id")).first()

        if not theme:
            return JsonResponse({"error": "Theme is required"}, status=400)

        return JsonResponse({
            "code": self.convert_assets_to_static(
                request.POST.get("code", ""),
                theme.slug,
            ),
        })

    def new_template_editor_save_view(self, request):
        if request.method != "POST":
            return JsonResponse(
                {"success": False, "message": "POST required"},
                status=405,
            )

        theme = Theme.objects.filter(pk=request.POST.get("theme_id")).first()
        template_type = request.POST.get("template_type")
        name = request.POST.get("name", "").strip()
        slug = request.POST.get("slug", "").strip()
        code = request.POST.get("code", "")

        if not theme:
            return JsonResponse(
                {"success": False, "message": "Theme is required."},
                status=400,
            )

        if not name:
            return JsonResponse(
                {"success": False, "message": "Name is required."},
                status=400,
            )

        if not slug:
            slug = slugify(unidecode(name))

        if not slug:
            return JsonResponse(
                {"success": False, "message": "Slug is required."},
                status=400,
            )

        if ThemeTemplate.objects.filter(theme=theme, slug=slug).exists():
            return JsonResponse(
                {
                    "success": False,
                    "message": "Template with this theme and slug already exists.",
                },
                status=400,
            )

        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=template_type or TemplateType.PARENT_PAGE,
            name=name,
            slug=slug,
            is_active=request.POST.get("is_active") == "1",
        )

        template_file_path = self.get_template_file_path(template)
        save_template_code(
            template=template,
            file_path=template_file_path,
            code=self.format_code_before_save(code),
            user=request.user,
            source="template_create",
        )

        return JsonResponse({
            "success": True,
            "message": "Template created successfully.",
            "file": str(template_file_path),
            "redirect_url": reverse(
                "admin:theme_manager_themetemplate_change",
                args=[template.pk],
            ),
            "change_url": reverse(
                "admin:theme_manager_themetemplate_change",
                args=[template.pk],
            ),
        })

    def new_template_editor_ai_transform_view(self, request):
        return self.template_editor_ai_transform_response(request)

    def template_editor_file_code_view(self, request, template_id):
        template = ThemeTemplate.objects.select_related("theme").get(pk=template_id)

        file_key = request.GET.get("file")

        if not file_key:
            return JsonResponse({"code": ""})

        file_path = template.theme.templates_map.get(file_key)

        if not file_path:
            return JsonResponse({"code": ""}, status=404)

        real_path = (
            Path(settings.BASE_DIR)
            / "static"
            / file_path
        )

        if not real_path.exists():
            return JsonResponse({"code": ""})

        code = self.read_template_code(real_path)

        return JsonResponse({
            "code": code,
            "file": file_path,
            "key": file_key,
        })

    def template_editor_convert_static_view(self, request, template_id):
        if request.method != "POST":
            return JsonResponse(
                {"error": "POST required"},
                status=405,
            )

        html = request.POST.get("code", "")

        template = ThemeTemplate.objects.select_related("theme").get(pk=template_id)

        converted_html = self.convert_assets_to_static(html, template.theme.slug,)

        return JsonResponse({
            "code": converted_html,
        })

    def template_editor_analyze_loads_view(self, request, template_id):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)
        if not self.has_change_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)

        ThemeTemplate.objects.only("pk").get(pk=template_id)
        return JsonResponse(analyze_template_loads(request.POST.get("code", "")))

    def template_editor_format_view(self, request, template_id):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        template = ThemeTemplate.objects.get(pk=template_id)
        if not self.has_change_permission(request, template):
            return JsonResponse({"error": "Permission denied"}, status=403)

        return JsonResponse({
            "code": format_template_code(request.POST.get("code", "")),
        })

    def template_editor_history_view(self, request, template_id):
        if request.method != "GET":
            return JsonResponse({"error": "GET required"}, status=405)

        template = ThemeTemplate.objects.select_related("theme").get(pk=template_id)
        if not self.has_change_permission(request, template):
            return JsonResponse({"error": "Permission denied"}, status=403)

        versions = []
        for version in template.versions.select_related("created_by")[:100]:
            created_at = timezone.localtime(version.created_at)
            versions.append({
                "id": version.pk,
                "created_at": created_at.isoformat(),
                "created_at_display": created_at.strftime("%d.%m.%Y %H:%M:%S"),
                "author": (
                    version.created_by.get_username()
                    if version.created_by
                    else "System"
                ),
                "source": version.source,
                "source_display": self.get_version_source_display(version.source),
                "line_count": version.line_count,
                "character_count": len(version.code),
            })

        return JsonResponse({
            "versions": versions,
            "count": len(versions),
        })

    def template_editor_history_compare_view(self, request, template_id):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        template = ThemeTemplate.objects.get(pk=template_id)
        if not self.has_change_permission(request, template):
            return JsonResponse({"error": "Permission denied"}, status=403)

        version = ThemeTemplateVersion.objects.filter(
            pk=request.POST.get("version_id"),
            template=template,
        ).first()
        if not version:
            return JsonResponse({"error": "Version not found"}, status=404)

        current_code = self.normalize_template_code(
            request.POST.get("current_code", "")
        )
        version_lines = version.code.splitlines()
        current_lines = current_code.splitlines()
        diff_lines = list(difflib.unified_diff(
            version_lines,
            current_lines,
            fromfile=f"Version {version.pk}",
            tofile="Current editor",
            lineterm="",
        ))

        return JsonResponse({
            "version_id": version.pk,
            "version_code": version.code,
            "diff": diff_lines,
            "added": sum(
                1 for line in diff_lines
                if line.startswith("+") and not line.startswith("+++")
            ),
            "removed": sum(
                1 for line in diff_lines
                if line.startswith("-") and not line.startswith("---")
            ),
            "is_identical": version.code == current_code,
        })

    def template_editor_history_restore_view(self, request, template_id):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        template = ThemeTemplate.objects.select_related("theme").get(pk=template_id)
        if not self.has_change_permission(request, template):
            return JsonResponse({"error": "Permission denied"}, status=403)

        version = ThemeTemplateVersion.objects.filter(
            pk=request.POST.get("version_id"),
            template=template,
        ).first()
        if not version:
            return JsonResponse({"error": "Version not found"}, status=404)

        current_editor_code = request.POST.get("current_code")
        if current_editor_code is not None:
            save_template_code(
                template=template,
                file_path=self.get_template_file_path(template),
                code=self.format_code_before_save(current_editor_code),
                user=request.user,
                source="restore_editor",
            )

        changed = save_template_code(
            template=template,
            file_path=self.get_template_file_path(template),
            code=self.format_code_before_save(version.code),
            user=request.user,
            source="restore",
        )

        return JsonResponse({
            "success": True,
            "changed": changed,
            "code": version.code,
            "message": (
                "Version restored successfully."
                if changed
                else "This version is already active."
            ),
        })

    @staticmethod
    def get_version_source_display(source):
        return {
            "admin_save": "Admin save",
            "ajax_save": "Editor save",
            "restore": "Before restore",
            "restore_editor": "Unsaved editor before restore",
            "extract_include": "Include extraction",
            "extract_page": "Page extraction",
            "template_create": "Template creation",
        }.get(source, source.replace("_", " ").title())

    def template_editor_extract_include_view(self, request, template_id):
        if request.method != "POST":
            return JsonResponse(
                {"error": "POST required"},
                status=405,
            )

        template = ThemeTemplate.objects.select_related("theme").get(pk=template_id)
        selected_code = request.POST.get("selected_code", "").strip()
        name = request.POST.get("name", "").strip()

        if not selected_code:
            return JsonResponse(
                {"error": "Select the code block you want to extract."},
                status=400,
            )

        if not name:
            return JsonResponse(
                {"error": "Block name is required."},
                status=400,
            )

        slug = slugify(unidecode(name))

        if not slug:
            return JsonResponse(
                {"error": "Block name must contain at least one valid character."},
                status=400,
            )

        if ThemeTemplate.objects.filter(theme=template.theme, slug=slug).exists():
            return JsonResponse(
                {"error": "A template with this slug already exists in this theme."},
                status=400,
            )

        include_template = ThemeTemplate.objects.create(
            theme=template.theme,
            template_type=TemplateType.INCLUDE_BLOCK,
            name=name,
            slug=slug,
            is_active=True,
        )

        include_file_path = self.get_template_file_path(include_template)
        save_template_code(
            template=include_template,
            file_path=include_file_path,
            code=self.format_code_before_save(selected_code),
            user=request.user,
            source="extract_include",
        )

        include_path = f"{template.theme.slug}/{slug}.html"

        return JsonResponse({
            "include": "{% include '" + include_path + "' %}",
            "name": include_template.name,
            "slug": include_template.slug,
            "file": str(include_file_path),
        })

    def template_editor_extract_page_block_view(self, request, template_id):
        if request.method != "POST":
            return JsonResponse(
                {"error": "POST required"},
                status=405,
            )

        template = ThemeTemplate.objects.select_related("theme").get(pk=template_id)
        selected_code = request.POST.get("selected_code", "").strip()
        name = request.POST.get("name", "").strip()

        if not selected_code:
            return JsonResponse(
                {"error": "Select the code block you want to extract."},
                status=400,
            )

        if not name:
            return JsonResponse(
                {"error": "Template name is required."},
                status=400,
            )

        slug = slugify(unidecode(name))

        if not slug:
            return JsonResponse(
                {"error": "Template name must contain at least one valid character."},
                status=400,
            )

        if ThemeTemplate.objects.filter(theme=template.theme, slug=slug).exists():
            return JsonResponse(
                {"error": "A template with this slug already exists in this theme."},
                status=400,
            )

        page_template = ThemeTemplate.objects.create(
            theme=template.theme,
            template_type=TemplateType.PARENT_PAGE,
            name=name,
            slug=slug,
            is_active=True,
        )

        parent_template_path = f"{template.theme.slug}/{template.slug}.html"
        page_code = (
            "{% extends '" + parent_template_path + "' %}\n"
            "{% load static %}\n"
            "{% load i18n %}\n"
            "{% load comments %}\n\n"
            "{% block main %}\n"
            + selected_code
            + "\n{% endblock %}\n"
        )

        page_file_path = self.get_template_file_path(page_template)
        save_template_code(
            template=page_template,
            file_path=page_file_path,
            code=self.format_code_before_save(page_code),
            user=request.user,
            source="extract_page",
        )

        return JsonResponse({
            "block": "{% block main %}{% endblock %}",
            "name": page_template.name,
            "slug": page_template.slug,
            "file": str(page_file_path),
        })

    def convert_assets_to_static(
            self,
            html: str,
            theme_slug: str,
    ) -> str:
        """
        Convert local CSS/JS/Image paths
        to Django {% static %} tags.

        Example:

            ../../assets/img/logo.png
            -> {% static 'sample-theme/assets/img/logo.png' %}

            assets/css/style.css
            -> {% static 'sample-theme/assets/css/style.css' %}

            /assets/js/main.js
            -> {% static 'sample-theme/assets/js/main.js' %}
        """

        has_full_document_tags = bool(
            re.search(r"<\s*(html|body)\b", html, flags=re.IGNORECASE)
        )

        soup = BeautifulSoup(html, "html.parser")

        # Static files
        static_extensions = (
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".svg",
            ".ico",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".webmanifest",
        )

        # HTML
        attrs_to_check = (
            "src",
            "href",
            "data-src",
            "data-background",
        )

        def should_skip(value: str) -> bool:
            """
            don't touch:
                {% static ... %}
                {{ variable }}
                http://
                https://
                //
                #
                mailto:
                tel:
            """

            if not value:
                return True

            value = value.strip()

            return (
                    value.startswith("{%")
                    or value.startswith("{{")
                    or "{% static" in value
                    or value.startswith("http://")
                    or value.startswith("https://")
                    or value.startswith("//")
                    or value.startswith("#")
                    or value.startswith("mailto:")
                    or value.startswith("tel:")
            )

        def normalize_static_path(value: str) -> str:
            """
            re:
                ../../assets/img/logo.png
                ../assets/img/logo.png
                /assets/img/logo.png
                assets/img/logo.png
            to
                sample-theme/assets/img/logo.png
            """

            value = value.strip()

            # прибираємо ../
            while value.startswith("../"):
                value = value[3:]

            # прибираємо /
            value = value.lstrip("/")

            # прибираємо static/
            if value.startswith("static/"):
                value = value[len("static/"):]

            # додаємо slug теми
            value = f"themes/{theme_slug}/{value}"

            return value

        for tag in soup.find_all(True):

            for attr in attrs_to_check:

                value = tag.get(attr)

                if should_skip(value):
                    continue

                clean_value = normalize_static_path(value)

                if clean_value.lower().endswith(static_extensions):
                    tag[attr] = (
                            "{% static '"
                            + clean_value
                            + "' %}"
                    )

        result = soup.prettify(formatter=None)

        if not has_full_document_tags:
            result = result.replace("<html>\n <head>\n </head>\n <body>\n", "")
            result = result.replace("\n </body>\n</html>", "")
            result = result.replace("<html><head></head><body>", "")
            result = result.replace("</body></html>", "")

        for tag in (
                "</meta>",
                "</link>",
                "</img>",
                "</input>",
                "</br>",
                "</hr>",
        ):
            result = result.replace(tag, "")

        formatted_lines = []

        for line in result.splitlines():
            stripped_line = line.lstrip()
            indent_level = len(line) - len(stripped_line)
            formatted_lines.append((" " * 4 * indent_level) + stripped_line.rstrip())

        result = "\n".join(formatted_lines).strip()

        # додаємо load static
        if "{% load static %}" not in result:
            result = "{% load static %}\n\n" + result

        return result

    def template_editor_save_view(self, request, template_id):
        if request.method != "POST":
            return JsonResponse(
                {"success": False, "message": "POST required"},
                status=405,
            )

        template = ThemeTemplate.objects.select_related("theme").get(
            pk=template_id
        )

        code = request.POST.get("code", "")

        template_file_path = self.get_template_file_path(template)

        save_template_code(
            template=template,
            file_path=template_file_path,
            code=self.format_code_before_save(code),
            user=request.user,
            source="ajax_save",
        )

        return JsonResponse({
            "success": True,
            "message": "Template saved successfully.",
            "file": str(template_file_path),
        })

    def template_editor_ai_transform_view(self, request, template_id):
        return self.template_editor_ai_transform_response(request, template_id=template_id)

    def template_editor_ai_transform_response(self, request, template_id=None):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        selected_code = request.POST.get("selected_code", "").strip()
        action = request.POST.get("action", "")
        text_prompt = request.POST.get("text_prompt", "").strip()
        html_prompt = request.POST.get("html_prompt", "").strip()
        image_prompt = request.POST.get("image_prompt", "").strip()
        component_type = request.POST.get("component_type", "").strip()
        category_id = request.POST.get("category_id", "").strip()
        category_title = request.POST.get("category_title", "").strip()
        category_slug = request.POST.get("category_slug", "").strip()
        category_instruction = request.POST.get("category_instruction", "").strip()

        languages = self.get_project_languages()

        if not selected_code:
            if action == "language_switcher":
                return JsonResponse({
                    "code": self.build_default_language_switcher(),
                })

            return JsonResponse({
                "error": "No selected code",
            }, status=400)


        if action == "generate_text":
            return self.generate_selected_text_response(
                selected_text=selected_code,
                text_prompt=text_prompt,
            )

        if action == "generate_html":
            return self.generate_selected_html_response(
                selected_code=selected_code,
                html_prompt=html_prompt,
            )

        if action == "generate_image":
            return self.generate_selected_image_response(
                selected_code=selected_code,
                image_prompt=image_prompt,
                template_id=template_id,
            )

        if action == "convert_component":
            return self.convert_selected_component_response(
                selected_code=selected_code,
                component_type=component_type,
                category_id=category_id,
                category_title=category_title,
                category_slug=category_slug,
                category_instruction=category_instruction,
            )

        prompt = f"""
    You are helping convert raw HTML into a Django template fragment.

    Task:
    {action}

    Rules:
    - Return ONLY the transformed code.
    - Do not explain.
    - Preserve existing HTML structure.
    - Preserve all CSS classes.
    - Preserve Bootstrap classes.
    - Preserve ids and data attributes.
    - Use valid Django template syntax.
    - Preserve icons, wrappers, classes, ids, aria attributes, and data attributes unless an id is repeated inside a loop; then make it dynamic with item.slug.
    - If adding translation, use {{% trans 'Text' %}}.
    - If adding static files, use {{% static 'path' %}}.
    - If language switcher is requested, preserve the selected structure but replace each language link href with working Django expressions.
    - If language switcher is requested, loop over the language_urls context variable.
    - Each language item contains code, name, url, and is_active.
    - Use language.url for href and language.is_active for active classes.
    - If language switcher is requested, never leave href="#".
    - Preserve the original labels and icons when mapping them to language items.
    - Do not wrap the result in markdown.
    - Do not add ```.

    Selected HTML:
    {selected_code}
    """

        if not getattr(settings, "OPENAI_API_KEY", ""):
            return JsonResponse({
                "error": "OpenAI API key is not configured. Add OPENAI_API_KEY to .env and restart the server."
            }, status=400)

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
            )
        except Exception as error:
            return JsonResponse({
                "error": f"AI transform failed: {error}"
            }, status=502)

        return JsonResponse({
            "code": response.output_text,
        })

    @staticmethod
    def normalize_component_type(component_type):
        return component_type.replace("_", "-").strip().lower()

    def get_component_conversion_prompt(
        self,
        component_type,
        category_id="",
        category_title="",
        category_slug="",
        category_instruction="",
    ):
        normalized_type = self.normalize_component_type(component_type)
        component = TemplateComponent.objects.filter(
            slug=normalized_type,
            is_active=True,
        ).first()

        if component and component.ai_conversion_prompt.strip():
            if normalized_type == "blog-category-children":
                return (
                    component.ai_conversion_prompt.strip()
                    + f"""

Selected parent blog category:
- id: {category_id or 0}
- title: {category_title or category_slug}
- slug: {category_slug}

Additional user instruction:
{category_instruction or "None"}
"""
                )
            return component.ai_conversion_prompt.strip()

        component_rules = {
            "breadcrumbs": """
- Convert the selected breadcrumb markup into a dynamic Django breadcrumb.
- Preserve the selected outer wrappers, classes, icons, separators, aria attributes, and list structure.
- Use title as the current page title, with safe fallbacks where useful.
- If a category object appears to be available, include a category link using category.get_absolute_url and category.name.
- Keep Home as a link to "/".
- Do not invent unrelated navigation items.
""",
            "pagination": """
- Convert the selected pagination markup into Django pagination using page_obj.
- Preserve wrappers, classes, icons, aria attributes, rel attributes, and visual structure.
- Load i18n and pagination, then use elided_page_range to build page_numbers.
- Use page_obj.has_previous, page_obj.previous_page_number, page_obj.number, page_obj.has_next, and page_obj.next_page_number.
- Render paginator.ELLIPSIS as disabled text without a link.
- Wrap the result in an if that only renders when page_obj exists and page_obj.paginator.num_pages > 1.
- Keep the current page active state in the same visual style as the selected markup.
""",
            "subscription": """
- Convert the selected subscription/newsletter form into a working CMS subscription form.
- Preserve wrappers, classes, fields, loading/error/sent message containers, icons, and layout.
- Set the form action to {% url 'core_manager:newsletter_subscribe' %}.
- Keep method="post" and include {% csrf_token %} inside the form.
- Ensure the email input has name="email", type="email", and required.
- Keep compatibility with BootstrapMade php-email-form behavior if those classes are present.
""",
            "contact_form": """
- Convert the selected contact form into a working CMS contact form.
- Preserve wrappers, classes, fields, loading/error/sent message containers, icons, and layout.
- Set the form action to {% url 'core_manager:contact_send' %}.
- Keep method="post" and include {% csrf_token %} inside the form.
- Ensure fields use name="name", name="email", name="subject", and name="message".
- Ensure the email field has type="email" and required.
- Add a hidden honeypot field named website inside the form, positioned off-screen, unless it already exists.
- Keep compatibility with BootstrapMade php-email-form behavior if those classes are present.
""",
            "comments": """
- Convert the selected comments/comment-form markup into django-contrib-comments markup.
- Preserve the selected visual section wrapper, classes, headings, and layout as much as possible.
- Include {% load comments %}.
- Do not use {% firstof ... as comment_object %}; django-comments needs a real model instance, not a rendered string.
- Use explicit branches for object, article, and page.
- In each branch, use get_comment_count, render_comment_list, and render_comment_form for the actual object in that branch.
- Keep existing comment section classes where possible.
""",
            "latest_blog_articles": """
- Convert the selected article/card/list markup into a reusable latest blog articles block.
- Preserve the selected outer wrappers, grid columns, card/list structure, CSS classes, icons, image wrappers, aria attributes, data attributes, and visual layout.
- Use the context variable latest_blog_articles. Never use articles for this module, because articles may already be the current blog category listing.
- Wrap the repeated markup in {% if latest_blog_articles %} and {% for article in latest_blog_articles %}.
- Use article.title for titles, article.intro|safe for intro/excerpt text, article.publish|date:"d.m.Y" for dates, article.category.title for category labels, and article.category.slug plus article.slug for URLs.
- Use {% url 'blog:post' category_slug=article.category.slug post_slug=article.slug %} for article links.
- Use {% url 'blog:category' category_slug=article.category.slug %} for category links when category links exist in the selected markup.
- If the selected markup contains images, render article.img_crop_mob and article.img_crop with a picture/img fallback while preserving selected image classes.
- If the selected markup contains comments, include {% load comments %} and use {% get_comment_count for article as comment_count %}.
- If the selected markup contains translated labels, include {% load i18n %} and use {% trans %} for static labels.
- Do not change the main category page variable articles.
""",
            "blog_category_children": f"""
- Convert the selected list/navigation markup into a dynamic list of direct child blog categories.
- Preserve the selected block's outer wrapper, list container, item wrapper, anchor classes, icons, spans, aria attributes, data attributes, dropdown hooks, and layout.
- Use {{% load blog_categories %}}.
- Use {{% get_blog_category_children {category_id or 0} as child_categories %}} before the repeated list markup.
- Loop with {{% for child_category in child_categories %}} and render one selected list item per child category.
- Use {{% url 'blog:category' category_slug=child_category.slug %}} for links.
- Use child_category.title for visible category text.
- If the selected item contains an icon, preserve the icon markup. If the icon content should come from the category, use child_category.icon only as a fallback and keep the original icon classes.
- Keep any static headings or wrapper labels that identify the parent category.
- The selected parent category is "{category_title or category_slug}" with slug "{category_slug}" and id {category_id or 0}.
- Additional user instruction: {category_instruction or "None"}.
- Follow the additional user instruction when it does not conflict with the required Django category loop.
- Do not render grandchildren unless the selected markup explicitly contains nested child lists.
""",
        }

        return component_rules.get(component_type) or component_rules.get(
            normalized_type
        )

    def convert_selected_component_response(
        self,
        selected_code,
        component_type,
        category_id="",
        category_title="",
        category_slug="",
        category_instruction="",
    ):
        if self.normalize_component_type(component_type) == "blog-category-children" and not category_id:
            return JsonResponse({
                "error": "Choose a parent blog category.",
            }, status=400)

        component_rules = self.get_component_conversion_prompt(
            component_type,
            category_id=category_id,
            category_title=category_title,
            category_slug=category_slug,
            category_instruction=category_instruction,
        )

        if not component_rules:
            return JsonResponse({
                "error": "Unknown component conversion type.",
            }, status=400)
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return JsonResponse({
                "error": "OpenAI API key is not configured. Add OPENAI_API_KEY to .env and restart the server."
            }, status=400)

        prompt = f"""
You are converting selected HTML into a working Django CMS template component.

Component type:
{component_type}

Component-specific rules:
{component_rules}

Global rules:
- Return only the final HTML/Django template code fragment.
- Do not explain your work.
- Do not use Markdown fences.
- Preserve the selected block's visual layout, wrappers, CSS classes, ids, icons, aria attributes, data attributes, and Bootstrap classes.
- Preserve existing text where it is still useful.
- Use valid Django template syntax.
- Do not add a full document, doctype, html, head, or body.
- Do not remove styling hooks unless they conflict with the required functionality.
- If adding Django tags, add only the load/url/csrf/comment tags required by the component.

Selected HTML:
{selected_code}
"""

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
            )
        except Exception as error:
            return JsonResponse({
                "error": f"AI component conversion failed: {error}",
            }, status=502)

        converted_code = (response.output_text or "").strip()
        converted_code = re.sub(
            r"^```(?:html|django|jinja|jinja2)?\s*",
            "",
            converted_code,
            flags=re.IGNORECASE,
        )
        converted_code = re.sub(r"\s*```$", "", converted_code).strip()
        if not converted_code:
            return JsonResponse({
                "error": "AI returned an empty component.",
            }, status=502)

        return JsonResponse({"code": converted_code})

    def generate_selected_text_response(self, selected_text, text_prompt):
        if not text_prompt:
            return JsonResponse({
                "error": "Describe the text you want to generate.",
            }, status=400)
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return JsonResponse({
                "error": "OpenAI API key is not configured. Add OPENAI_API_KEY to .env and restart the server."
            }, status=400)

        prompt = f"""
Rewrite or replace the selected website text according to the instruction.

Instruction:
{text_prompt}

Selected text:
{selected_text}

Rules:
- Return only the final text.
- Do not explain your work.
- Do not use Markdown fences.
- Do not add quotation marks around the result.
- Do not return HTML or Django template tags.
- Follow the requested language, tone and approximate size.
"""

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
            )
        except Exception as error:
            return JsonResponse({
                "error": f"AI text generation failed: {error}",
            }, status=502)

        generated_text = (response.output_text or "").strip()
        generated_text = re.sub(r"^```(?:text)?\s*", "", generated_text)
        generated_text = re.sub(r"\s*```$", "", generated_text).strip()
        if not generated_text:
            return JsonResponse({
                "error": "AI returned an empty text.",
            }, status=502)

        return JsonResponse({"code": generated_text})

    def generate_selected_html_response(self, selected_code, html_prompt):
        if not html_prompt:
            return JsonResponse({
                "error": "Describe how you want to change the selected code.",
            }, status=400)
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return JsonResponse({
                "error": "OpenAI API key is not configured. Add OPENAI_API_KEY to .env and restart the server."
            }, status=400)

        prompt = f"""
Edit the selected website template code according to the instruction.

Instruction:
{html_prompt}

Selected code:
{selected_code}

Rules:
- Return only the final HTML/Django template code fragment.
- Do not explain your work.
- Do not use Markdown fences.
- Do not add a full document, doctype, html, head, or body unless the selected code already contains them or the instruction explicitly asks for them.
- Preserve existing CSS classes unless the instruction explicitly asks to change them.
- Preserve existing ids, data attributes, aria attributes, href/src values, and Bootstrap classes unless the requested change requires editing them.
- Preserve Django template syntax, including {{{{ ... }}}}, {{% ... %}}, comments, blocks, includes, static tags, translation tags, and loops.
- Keep valid nesting for HTML tags and Django template blocks.
- If adding Bootstrap components, use Bootstrap-compatible markup and keep the surrounding selected structure.
- If adding text, keep the language and tone implied by the selected code unless the instruction says otherwise.
- If the request is ambiguous, make the smallest useful change.
"""

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
            )
        except Exception as error:
            return JsonResponse({
                "error": f"AI HTML generation failed: {error}",
            }, status=502)

        generated_code = (response.output_text or "").strip()
        generated_code = re.sub(r"^```(?:html|django|jinja|jinja2)?\s*", "", generated_code, flags=re.IGNORECASE)
        generated_code = re.sub(r"\s*```$", "", generated_code).strip()
        if not generated_code:
            return JsonResponse({
                "error": "AI returned an empty code fragment.",
            }, status=502)

        return JsonResponse({"code": generated_code})

    def generate_selected_image_response(
        self,
        selected_code,
        image_prompt,
        template_id,
    ):
        if not template_id:
            return JsonResponse({
                "error": "Save the template before generating an image.",
            }, status=400)
        if not image_prompt:
            return JsonResponse({
                "error": "Describe the image you want to generate.",
            }, status=400)
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return JsonResponse({
                "error": "OpenAI API key is not configured. Add OPENAI_API_KEY to .env and restart the server."
            }, status=400)

        template = ThemeTemplate.objects.select_related("theme").get(pk=template_id)
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            result = generate_replacement_image(
                client=client,
                selected_code=selected_code,
                user_prompt=image_prompt,
                theme_slug=template.theme.slug,
            )
        except ImageGenerationError as error:
            return JsonResponse({"error": str(error)}, status=400)
        except Exception as error:
            return JsonResponse({
                "error": f"AI image generation failed: {error}",
            }, status=502)

        return JsonResponse(result)

    def get_project_languages(self):
        return [
            {
                "code": code,
                "name": name,
            }
            for code, name in settings.LANGUAGES
        ]

    def build_default_language_switcher(self):
        return f'''
    <li class="d-block d-sm-none mt-3 text-center">
        {{% for language in language_urls %}}
            <a href="{{{{ language.url }}}}"
               class="mx-3 {{% if language.is_active %}}text-danger{{% endif %}}">
                {{{{ language.code|upper }}}}
            </a>{{% if not forloop.last %}} / {{% endif %}}
        {{% endfor %}}
    </li>
    '''
