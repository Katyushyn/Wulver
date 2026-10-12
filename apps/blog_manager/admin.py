from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone, translation
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
import json
import re
from pathlib import Path
from modeltranslation.admin import TabbedTranslationAdmin
from openai import OpenAI

from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.theme_manager.models import ThemeTemplate, TemplateType
from apps.core_manager.admin_mixins import SingletonAdminMixin
from apps.core_manager.tree_sorting import (
    apply_tree_order,
    build_tree_nodes,
    flatten_tree,
    parse_tree_request,
)
from apps.core_manager.admin_links import get_cms_link_options

from .models import (
    Article,
    ArticleImage,
    BlogSettings,
    Category,
    ImageModule,
    LatestArticlesModule,
    Tag,
    TagModule,
)
from .image_module_forms import ImageModuleAdminForm
from .image_module_storage import (
    delete_manifest_files,
    delete_module_storage,
    format_bytes,
    store_image_uploads,
    validate_image_uploads,
)
from .article_preview import ArticlePreviewError, render_article_body_preview


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
    "checkbox",
    "radio",
    "select",
    "multiselect",
    "hidden",
}

ARTICLE_EXTRA_CHOICE_TYPES = {"select", "multiselect", "radio"}

def article_image_payload(image):
    try:
        file_size = image.image.size
    except (FileNotFoundError, OSError, ValueError):
        file_size = 0

    return {
        "id": image.pk,
        "url": image.image.url,
        "name": Path(image.image.name).name,
        "alt": image.alt_text,
        "width": image.width,
        "height": image.height,
        "sort_order": image.sort_order,
        "size": file_size,
        "size_display": format_bytes(file_size),
    }

def normalize_article_extra_fields_schema(schema):
    if not isinstance(schema, dict):
        return {}

    normalized = {}

    for name, config in schema.items():
        if not isinstance(name, str) or not name.replace("_", "").isalnum():
            continue

        if not name or name[0].isdigit() or not isinstance(config, dict):
            continue

        field_type = config.get("type")
        label = config.get("label")

        if field_type not in ARTICLE_EXTRA_FIELD_TYPES:
            continue

        if not isinstance(label, str) or not label.strip():
            continue

        field = {
            "name": name,
            "label": label.strip(),
            "type": field_type,
            "required": config.get("required") is True,
            "default": config.get("default") if isinstance(config.get("default"), str) else "",
            "placeholder": config.get("placeholder") if isinstance(config.get("placeholder"), str) else "",
            "help_text": config.get("help_text") if isinstance(config.get("help_text"), str) else "",
        }

        choices = config.get("choices")
        if field_type in ARTICLE_EXTRA_CHOICE_TYPES:
            if not isinstance(choices, list):
                continue

            field["choices"] = [
                choice.strip()
                for choice in choices
                if isinstance(choice, str) and choice.strip()
            ]

            if not field["choices"]:
                continue
        elif field_type == "checkbox" and choices not in (None, ""):
            if not isinstance(choices, list):
                continue

            field["choices"] = [
                choice.strip()
                for choice in choices
                if isinstance(choice, str) and choice.strip()
            ]

            if not field["choices"]:
                continue

        normalized[name] = field

    return normalized


@admin.register(BlogSettings)
class BlogSettingsAdmin(SingletonAdminMixin, ModelAdmin):
    autocomplete_fields = (
        "default_category_template",
        "default_paginated_category_template",
        "default_article_template",
    )
    fieldsets = (
        (
            _("Templates"),
            {
                "fields": (
                    "default_category_template",
                    "default_paginated_category_template",
                    "default_article_template",
                )
            },
        ),
        (
            _("Category SEO"),
            {
                "fields": (
                    "default_category_schema_graph",
                )
            },
        ),
        (
            _("Article SEO"),
            {
                "description": _(
                    "Base JSON-LD settings for every article. Article-specific values "
                    "such as headline, description, language, URL, dates, image, "
                    "category and tags are generated automatically."
                ),
                "fields": (
                    "default_article_schema_graph",
                )
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        queryset = ThemeTemplate.objects.filter(
            theme__is_active=True,
            is_active=True,
        )

        if db_field.name in (
            "default_category_template",
            "default_paginated_category_template",
        ):
            kwargs["queryset"] = queryset.filter(
                template_type=TemplateType.CHILDREN_BLOG,
            )

        if db_field.name == "default_article_template":
            kwargs["queryset"] = queryset.filter(
                template_type=TemplateType.CHILDREN_ARTICLE,
            )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return not BlogSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        settings = BlogSettings.get_solo()

        return redirect(
            reverse(
                "admin:blog_manager_blogsettings_change",
                args=[settings.pk],
            )
        )


class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = "__all__"


@admin.register(LatestArticlesModule)
class LatestArticlesModuleAdmin(ModelAdmin):
    list_display = (
        "name",
        "slug",
        "articles_count",
        "ordering",
        "include_descendants",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "ordering", "include_descendants")
    search_fields = ("name", "slug", "categories__title", "tags__title")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("categories", "tags", "authors")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            _("General"),
            {
                "fields": (
                    "name",
                    "slug",
                    "categories",
                    "tags",
                    "authors",
                    "include_descendants",
                    "articles_count",
                    "ordering",
                    "is_active",
                )
            },
        ),
        (
            _("System"),
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(TagModule)
class TagModuleAdmin(ModelAdmin):
    list_display = (
        "name",
        "slug",
        "source",
        "tags_count",
        "ordering",
        "class_mode",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "source", "ordering", "class_mode")
    search_fields = ("name", "slug", "classes")
    prepopulated_fields = {"slug": ("name",)}
    radio_fields = {"class_mode": admin.HORIZONTAL}
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            _("General"),
            {
                "fields": (
                    "name",
                    "slug",
                    "source",
                    "tags_count",
                    "ordering",
                    "is_active",
                )
            },
        ),
        (
            _("Classes"),
            {
                "fields": ("classes", "class_mode"),
                "description": _(
                    "Configure how comma-separated CSS classes are assigned to tags."
                ),
            },
        ),
        (
            _("System"),
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(ImageModule)
class ImageModuleAdmin(ModelAdmin):
    form = ImageModuleAdminForm

    class Media:
        css = {"all": ("blog_manager/css/image-module-admin.css",)}
        js = ("blog_manager/js/image-module-admin.js",)

    list_display = (
        "name",
        "slug",
        "display_mode",
        "image_count_display",
        "storage_size_display",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "display_mode")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = (
        "image_gallery",
        "storage_folder",
        "storage_size_display",
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
                    "display_mode",
                    "images_count",
                    "is_active",
                )
            },
        ),
        (
            _("Images"),
            {
                "fields": (
                    "uploads",
                    "manifest_editor",
                    "image_gallery",
                    "storage_size_display",
                ),
                "description": _(
                    "Upload multiple images, edit alt text, change their order, "
                    "disable individual images or remove them from the module."
                ),
            },
        ),
        (
            _("System"),
            {
                "classes": ("collapse",),
                "fields": (
                    "storage_folder",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def image_count_display(self, obj):
        return len(obj.manifest or [])

    image_count_display.short_description = _("Files")

    def storage_size_display(self, obj):
        return format_bytes(obj.storage_size if obj and obj.pk else 0)

    storage_size_display.short_description = _("Storage used")

    def storage_folder(self, obj):
        if not obj or not obj.pk:
            return _("The folder is created after the module is saved.")
        return obj.storage_prefix

    storage_folder.short_description = _("Storage folder")

    def image_gallery(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<div class="image-module-gallery is-empty">{}</div>',
                _("Save the module, then upload images."),
            )
        return format_html(
            '<div class="image-module-gallery" data-media-url="{}"></div>',
            settings.MEDIA_URL,
        )

    image_gallery.short_description = _("Module images")

    def save_model(self, request, obj, form, change):
        old_manifest = []
        if change and obj.pk:
            old_manifest = list(
                ImageModule.objects.filter(pk=obj.pk)
                .values_list("manifest", flat=True)
                .first()
                or []
            )

        retained_manifest = list(form.cleaned_data.get("manifest_editor") or [])
        retained_ids = {item.get("id") for item in retained_manifest}
        removed = [
            item for item in old_manifest
            if item.get("id") not in retained_ids
        ]

        obj.manifest = retained_manifest
        super().save_model(request, obj, form, change)
        delete_manifest_files(obj, removed)

        uploads = form.cleaned_data.get("uploads") or []
        if uploads:
            obj.manifest = retained_manifest + store_image_uploads(obj, uploads)
            obj.save(update_fields=("manifest", "updated_at"))
            messages.success(
                request,
                _("Uploaded %(count)s image files.") % {"count": len(uploads)},
            )

    def delete_model(self, request, obj):
        delete_module_storage(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            delete_module_storage(obj)
        super().delete_queryset(request, queryset)


class ArticleAdminForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = "__all__"
        widgets = {
            "article_extra_fields": forms.HiddenInput(
                attrs={"class": "article-extra-fields-data"}
            ),
            "intro": WysiwygWidget(),
            "body": UnfoldAdminTextareaWidget(attrs={
                "class": "codemirror-article-body",
                "rows": 35,
                "spellcheck": "false",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["article_extra_fields"].widget.attrs[
            "data-schema-url"
        ] = reverse("admin:blog_manager_article_extra_fields_schema")

        ai_edit_url = reverse("admin:blog_manager_article_ai_edit_text")
        cms_link_options_url = reverse(
            "admin:blog_manager_article_cms_link_options"
        )
        body_preview_url = reverse(
            "admin:blog_manager_article_body_preview"
        )
        css_classes_url = reverse(
            "admin:blog_manager_article_css_classes"
        )
        self.fields["schema_graph"].help_text = _(
            "Optional article-specific JSON-LD overrides. Leave empty to use the "
            "automatically generated article schema. Values entered here are merged "
            "last and override generated values with the same names."
        )
        for field_name, field in self.fields.items():
            if field_name == "body" or field_name.startswith("body_"):
                classes = field.widget.attrs.get("class", "").split()
                if "codemirror-article-body" not in classes:
                    classes.append("codemirror-article-body")
                field.widget.attrs["class"] = " ".join(filter(None, classes))
                field.widget.attrs["data-ai-edit-url"] = ai_edit_url
                field.widget.attrs["data-cms-link-options-url"] = cms_link_options_url
                field.widget.attrs["data-preview-url"] = body_preview_url
                field.widget.attrs["data-css-classes-url"] = css_classes_url
                field.widget.attrs["data-article-id"] = self.instance.pk or ""
                field.widget.attrs["data-language"] = (
                    field_name.rsplit("_", 1)[-1]
                    if field_name.startswith("body_")
                    else settings.LANGUAGE_CODE
                )

    def _get_selected_category(self):
        category_id = None

        if self.is_bound:
            category_id = self.data.get(self.add_prefix("category"))
        elif self.instance and self.instance.pk:
            category_id = self.instance.category_id

        if not category_id:
            return None

        return (
            Category.objects
            .select_related("article_theme_template")
            .filter(pk=category_id)
            .first()
        )

    def _get_article_extra_fields_schema(self):
        category = self._get_selected_category()

        if not category or not category.article_theme_template_id:
            return {}

        return normalize_article_extra_fields_schema(
            category.article_theme_template.article_extra_fields_schema
        )

    def clean_article_extra_fields(self):
        values = self.cleaned_data.get("article_extra_fields") or {}

        if not isinstance(values, dict):
            raise forms.ValidationError(_("Article extra fields must be a JSON object."))

        schema = self._get_article_extra_fields_schema()

        if not schema:
            return {}

        cleaned_values = {}

        for name, field in schema.items():
            value = values.get(name, field.get("default", ""))
            field_type = field["type"]
            is_required = field.get("required") is True

            if field_type == "checkbox":
                choices = field.get("choices", [])
                checked = value is True or value == "true" or value in choices
                cleaned_values[name] = choices[0] if checked and choices else checked
                if is_required and not cleaned_values[name]:
                    raise forms.ValidationError(
                        _("Field '%(field)s' is required."),
                        params={"field": field["label"]},
                    )
                continue

            if field_type == "multiselect":
                choices = set(field.get("choices", []))

                if not isinstance(value, list):
                    value = []

                cleaned_values[name] = [
                    item
                    for item in value
                    if isinstance(item, str) and item in choices
                ]
                if is_required and not cleaned_values[name]:
                    raise forms.ValidationError(
                        _("Field '%(field)s' is required."),
                        params={"field": field["label"]},
                    )
                continue

            if not isinstance(value, str):
                value = ""

            value = value.strip()

            if field_type in {"select", "radio"}:
                choices = set(field.get("choices", []))
                cleaned_values[name] = value if value in choices else ""
                if is_required and not cleaned_values[name]:
                    raise forms.ValidationError(
                        _("Field '%(field)s' is required."),
                        params={"field": field["label"]},
                    )
                continue

            if is_required and not value:
                raise forms.ValidationError(
                    _("Field '%(field)s' is required."),
                    params={"field": field["label"]},
                )

            if field_type == "number":
                if not value:
                    cleaned_values[name] = None
                    continue

                try:
                    number_value = float(value)
                except ValueError:
                    raise forms.ValidationError(
                        _("Field '%(field)s' must be a number."),
                        params={"field": field["label"]},
                    )

                cleaned_values[name] = (
                    int(number_value) if number_value.is_integer() else number_value
                )
                continue

            if field_type == "email" and value:
                forms.EmailField().clean(value)
                cleaned_values[name] = value
                continue

            if field_type == "url" and value:
                cleaned_values[name] = forms.URLField().clean(value)
                continue

            cleaned_values[name] = value

        return cleaned_values


class ImagePreviewMixin:
    def image_preview(self, obj):
        image = getattr(obj, "img_crop", None) or getattr(obj, "img", None)

        if not image:
            return "-"

        return format_html(
            '<img src="{}" style="max-width: 120px; max-height: 80px; border-radius: 6px; object-fit: cover;" />',
            image.url,
        )

    image_preview.short_description = _("Preview")

class TreeOrderedCategoryChangeList(ChangeList):
    def get_ordering(self, request, queryset):
        if not queryset.exists():
            return super().get_ordering(request, queryset)

        return ("_tree_order",)

@admin.register(Category)
class CategoryAdmin(ImagePreviewMixin, ModelAdmin, TabbedTranslationAdmin):
    change_list_template = "admin/blog_manager/category/change_list.html"
    sortable_by = ()
    list_before_template = "admin/shared/tree_sortable.html"
    class Media:
        css = {
            "all": (
                "admin_tree_sorting/tree-sortable.css",
            )
        }
        js = (
            "vendor/sortablejs/Sortable.min.js",
            "admin_tree_sorting/tree-sortable.js",
        )
    form = CategoryAdminForm

    autocomplete_fields = (
        "parent",
        "theme_template",
        "paginated_theme_template",
        "article_theme_template",
    )
    filter_horizontal = (
        "tags",
    )
    list_display = (
        "tree_title",
        "parent",
        "slug",
        "noindex",
        "image_preview",
        "created",
        "updated",
    )
    list_filter = (
        "noindex",
        "created",
        "updated",
    )
    search_fields = (
        "title",
        "slug",
        "description",
        "intro",
    )
    prepopulated_fields = {
        "slug": ("title",),
    }
    readonly_fields = (
        "img_crop",
        "img_crop_mob",
        "created",
        "updated",
    )
    fieldsets = (
        (
            _("General"),
            {
                "fields": (
                    "title",
                    "slug",
                    "description",
                    "intro",
                    "keywords",
                    "parent",
                    "theme_template",
                    "paginated_theme_template",
                    "article_theme_template",
                    "tags",
                    "icon",
                    "sort_order",
                    "articles_per_page",
                )
            },
        ),
        (
            _("SEO"),
            {
                "fields": (
                    "preview_image",
                    "seo_title",
                    "og_type",
                    "schema_graph",
                    "canonical_allowed_params",
                    "noindex",
                )
            },
        ),
        (
            _("Images"),
            {
                "fields": (
                    "img",
                    "img_crop",
                    "img_crop_mob",
                )
            },
        ),
        (
            _("System"),
            {
                "classes": ("collapse",),
                "fields": (
                    "created",
                    "updated",
                ),
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "drag-order/",
                self.admin_site.admin_view(self.drag_order_view),
                name="blog_manager_category_drag_order",
            ),
        ]
        return custom_urls + urls

    def get_drag_trees(self):
        categories = list(
            Category.objects.select_related("parent")
            .order_by("parent_id", "sort_order", "pk")
        )
        if not categories:
            return []

        return [{
            "title": _("Category tree"),
            "scope_id": "categories",
            "group": "blog-categories",
            "save_url": reverse("admin:blog_manager_category_drag_order"),
            "nodes": build_tree_nodes(
                categories,
                lambda category: category.title,
                "admin:blog_manager_category_change",
            ),
        }]

    def drag_order_view(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required."}, status=405)
        if not self.has_change_permission(request):
            return JsonResponse({"error": "Permission denied."}, status=403)

        try:
            _payload, tree = parse_tree_request(request)
            expected_ids = set(Category.objects.values_list("pk", flat=True))
            ordered_rows = flatten_tree(tree, expected_ids)
            updated = apply_tree_order(Category, ordered_rows)
        except ValidationError as error:
            message = getattr(error, "message", None) or str(error)
            return JsonResponse({"error": message}, status=400)

        return JsonResponse({"success": True, "updated": updated})

    def get_changelist(self, request, **kwargs):
        return TreeOrderedCategoryChangeList

    @staticmethod
    def get_tree_ordered_ids():
        categories = list(
            Category.objects.values(
                "id",
                "parent_id",
                "sort_order",
            )
        )
        children_map = {}

        for category in categories:
            children_map.setdefault(category["parent_id"], []).append(category)

        for children in children_map.values():
            children.sort(key=lambda item: (item["sort_order"], item["id"]))

        ordered_ids = []
        visited = set()

        def append_branch(parent_id=None):
            for category in children_map.get(parent_id, []):
                if category["id"] in visited:
                    continue

                visited.add(category["id"])
                ordered_ids.append(category["id"])
                append_branch(category["id"])

        append_branch()

        for category in sorted(
            categories,
            key=lambda item: (item["sort_order"], item["id"]),
        ):
            if category["id"] not in visited:
                visited.add(category["id"])
                ordered_ids.append(category["id"])
                append_branch(category["id"])

        return ordered_ids

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            "parent",
            "parent__parent",
        )
        ordered_ids = self.get_tree_ordered_ids()

        if not ordered_ids:
            return queryset

        tree_order = Case(
            *[
                When(pk=category_id, then=position)
                for position, category_id in enumerate(ordered_ids)
            ],
            default=len(ordered_ids),
            output_field=IntegerField(),
        )

        return queryset.annotate(_tree_order=tree_order).order_by("_tree_order")
    def tree_title(self, obj):
        level = 0
        parent = obj.parent

        while parent:
            level += 1
            parent = parent.parent

            if level > 20:
                break

        if not level:
            return obj.title

        return format_html(
            '<span style="display:inline-block; margin-left:{}px; margin-right:6px; opacity:.65;">&#8627;</span>{}',
            level * 18,
            obj.title,
        )

    tree_title.short_description = _("Category")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            object_id = request.resolver_match.kwargs.get("object_id")
            queryset = Category.objects.order_by("parent_id", "sort_order", "id")

            if object_id:
                current_category = Category.objects.filter(pk=object_id).first()

                if current_category:
                    excluded_ids = {current_category.pk}
                    pending_ids = [current_category.pk]

                    while pending_ids:
                        child_ids = list(
                            Category.objects.filter(parent_id__in=pending_ids)
                            .values_list("pk", flat=True)
                        )
                        pending_ids = [
                            child_id
                            for child_id in child_ids
                            if child_id not in excluded_ids
                        ]
                        excluded_ids.update(pending_ids)

                    queryset = queryset.exclude(pk__in=excluded_ids)

            kwargs["queryset"] = queryset

        if db_field.name in (
            "theme_template",
            "paginated_theme_template",
            "article_theme_template",
        ):
            kwargs["queryset"] = ThemeTemplate.objects.filter(
                theme__is_active=True,
                is_active=True,
            )

            if db_field.name in (
                "theme_template",
                "paginated_theme_template",
            ):
                kwargs["queryset"] = kwargs["queryset"].filter(
                    template_type=TemplateType.CHILDREN_BLOG,
                )

            if db_field.name == "article_theme_template":
                kwargs["queryset"] = kwargs["queryset"].filter(
                    template_type=TemplateType.CHILDREN_ARTICLE,
                )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        Category.normalize_sort_order()

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "drag_trees": self.get_drag_trees(),
        }
        response = super().changelist_view(
            request,
            extra_context=extra_context,
        )

        if request.method == "POST":
            Category.normalize_sort_order()

        return response


@admin.register(Article)
class ArticleAdmin(ImagePreviewMixin, ModelAdmin, TabbedTranslationAdmin):
    form = ArticleAdminForm

    class Media:
        css = {
            "all": (
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css",
                "blog_manager/css/article-extra-fields.css",
                "admin/css/cms-link-browser.css",
                "blog_manager/css/article-body-editor.css",
                "blog_manager/css/article-content-images.css",
            )
        }
        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/xml/xml.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/js-beautify/1.15.4/beautify-html.min.js",
            "blog_manager/js/article-extra-fields.js",
            "admin/js/cms-link-browser.js",
            "blog_manager/js/article-body-editor.js",
            "blog_manager/js/article-content-images.js",
        )

    autocomplete_fields = (
        "category",
        "theme_template",
    )
    filter_horizontal = (
        "tags",
    )
    list_display = (
        "title",
        "category",
        "status",
        "is_published",
        "noindex",
        "publish",
        "author",
        "image_preview",
    )
    list_filter = (
        "status",
        "is_published",
        "noindex",
        "category",
        "publish",
        "created",
        "updated",
    )
    search_fields = (
        "title",
        "slug",
        "description",
        "intro",
        "body",
    )
    prepopulated_fields = {
        "slug": ("title",),
    }
    readonly_fields = (
        "author",
        "article_extra_fields_form",
        "article_content_images_manager",
        "img_crop",
        "img_crop_mob",
        "created",
        "updated",
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
                    "category",
                    "theme_template",
                    "status",
                    "tags",
                    "is_published",
                    "publish",
                    "author",
                )
            },
        ),
        (
            _("Extra fields"),
            {
                "fields": (
                    "article_extra_fields_form",
                    "article_extra_fields",
                )
            },
        ),
        (
            _("Content"),
            {
                "fields": (
                    "intro",
                    "body",
                    "article_content_images_manager",
                )
            },
        ),
        (
            _("Images"),
            {
                "fields": (
                    "img",
                    "img_crop",
                    "img_crop_mob",
                )
            },
        ),
        (
            _("SEO"),
            {
                "classes": ("collapse",),
                "fields": (
                    "seo_title",
                    "preview_image",
                    "og_type",
                    "schema_graph",
                    "canonical_allowed_params",
                    "noindex",
                ),
            },
        ),
        (
            _("System"),
            {
                "classes": ("collapse",),
                "fields": (
                    "created",
                    "updated",
                ),
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "extra-fields-schema/",
                self.admin_site.admin_view(self.extra_fields_schema_view),
                name="blog_manager_article_extra_fields_schema",
            ),
            path(
                "ai-edit-text/",
                self.admin_site.admin_view(self.ai_edit_text_view),
                name="blog_manager_article_ai_edit_text",
            ),
            path(
                "cms-link-options/",
                self.admin_site.admin_view(self.cms_link_options_view),
                name="blog_manager_article_cms_link_options",
            ),
            path(
                "body-preview/",
                self.admin_site.admin_view(self.body_preview_view),
                name="blog_manager_article_body_preview",
            ),
            path(
                "css-classes/",
                self.admin_site.admin_view(self.css_classes_view),
                name="blog_manager_article_css_classes",
            ),
            path(
                "<int:object_id>/content-images/",
                self.admin_site.admin_view(self.content_images_view),
                name="blog_manager_article_content_images",
            ),
        ]
        return custom_urls + urls

    def css_classes_view(self, request):
        if request.method != "GET":
            return JsonResponse({"error": "GET required."}, status=405)
        if not self.has_view_or_change_permission(request):
            return JsonResponse({"error": "Permission denied."}, status=403)

        category = (
            Category.objects
            .select_related("article_theme_template")
            .filter(pk=request.GET.get("category_id"))
            .first()
        )
        if not category:
            return JsonResponse({"error": "Select an article category first."}, status=400)

        template = None
        template_id = request.GET.get("theme_template_id")
        if template_id:
            template = ThemeTemplate.objects.filter(
                pk=template_id,
                template_type=TemplateType.CHILDREN_ARTICLE,
                is_active=True,
            ).first()
            if not template:
                return JsonResponse({"error": "Selected article template was not found."}, status=400)
        elif category.article_theme_template_id:
            template = category.article_theme_template
        else:
            template = BlogSettings.get_solo().default_article_template

        if not template:
            return JsonResponse({"error": "No article template is configured for this category."}, status=400)

        return JsonResponse({
            "classes": template.css_classes or [],
            "template": {
                "id": template.pk,
                "name": template.name,
            },
        })

    def cms_link_options_view(self, request):
        if request.method != "GET":
            return JsonResponse({"error": "GET required."}, status=405)
        if not self.has_view_or_change_permission(request):
            return JsonResponse({"error": "Permission denied."}, status=403)

        try:
            page = max(1, int(request.GET.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            payload = get_cms_link_options(
                request.GET.get("type", ""),
                query=request.GET.get("q", ""),
                page=page,
                language=request.GET.get("language"),
            )
        except ValueError:
            return JsonResponse({"error": "Unknown content type."}, status=400)
        return JsonResponse(payload)

    def body_preview_view(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required."}, status=405)

        article = None
        article_id = request.POST.get("article_id")
        if article_id:
            article = (
                Article.objects
                .select_related("category", "theme_template", "theme_template__theme")
                .filter(pk=article_id)
                .first()
            )
            if not article:
                return JsonResponse({"error": "Article not found."}, status=404)
            if not self.has_change_permission(request, article):
                return JsonResponse({"error": "Permission denied."}, status=403)
        elif not self.has_add_permission(request):
            return JsonResponse({"error": "Permission denied."}, status=403)

        category = (
            Category.objects
            .select_related("article_theme_template", "article_theme_template__theme")
            .filter(pk=request.POST.get("category_id"))
            .first()
        )
        if not category:
            return JsonResponse({"error": "Select an article category first."}, status=400)

        template_id = request.POST.get("theme_template_id")
        selected_template = None
        if template_id:
            selected_template = (
                ThemeTemplate.objects
                .select_related("theme")
                .filter(
                    pk=template_id,
                    template_type=TemplateType.CHILDREN_ARTICLE,
                    is_active=True,
                )
                .first()
            )
            if not selected_template:
                return JsonResponse({"error": "Selected article template was not found."}, status=400)

        if article is None:
            preview_time = timezone.now()
            article = Article(
                pk=0,
                slug="article-preview",
                description="Article preview",
                intro="",
                is_published=True,
                publish=preview_time,
                created=preview_time,
                updated=preview_time,
                author=request.user,
            )

        language = request.POST.get("language")
        available_languages = {code for code, _name in settings.LANGUAGES}
        if language not in available_languages:
            language = settings.LANGUAGE_CODE

        article.category = category
        article.theme_template = selected_template
        title = request.POST.get("title", "").strip() or article.title or "Article preview"
        body_html = request.POST.get("body_html", "")

        try:
            with translation.override(language):
                setattr(article, f"title_{language}", title)
                setattr(article, f"body_{language}", body_html)
                rendered = render_article_body_preview(request, article, body_html)
        except ArticlePreviewError as error:
            return JsonResponse({"error": str(error)}, status=400)
        except Exception as error:
            if settings.DEBUG:
                return JsonResponse({"error": str(error)}, status=400)
            return JsonResponse({"error": "The article preview could not be rendered."}, status=400)

        return HttpResponse(rendered, content_type="text/html; charset=utf-8")

    def ai_edit_text_view(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required."}, status=405)
        if not self.has_change_permission(request):
            return JsonResponse({"error": "Permission denied."}, status=403)

        selected_text = str(request.POST.get("selected_text") or "").strip()
        text_prompt = str(request.POST.get("text_prompt") or "").strip()
        if not selected_text:
            return JsonResponse({"error": "Select the text you want to edit."}, status=400)
        if not text_prompt:
            return JsonResponse({"error": "Describe how the selected text should be changed."}, status=400)
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return JsonResponse({
                "error": "OpenAI API key is not configured. Add OPENAI_API_KEY to .env and restart the server.",
            }, status=400)

        prompt = f"""
Rewrite or replace the selected article text according to the instruction.

Instruction:
{text_prompt}

Selected text:
{selected_text}

Rules:
- Return only the final replacement text.
- Do not explain your work.
- Do not use Markdown fences.
- Do not add quotation marks around the result.
- Do not add HTML unless the instruction explicitly requests HTML.
- Preserve the requested language, tone, meaning and approximate size.
"""

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
            )
        except Exception as error:
            return JsonResponse({
                "error": f"AI text editing failed: {error}",
            }, status=502)

        generated_text = (response.output_text or "").strip()
        generated_text = re.sub(r"^```(?:text|html)?\s*", "", generated_text)
        generated_text = re.sub(r"\s*```$", "", generated_text).strip()
        if not generated_text:
            return JsonResponse({"error": "AI returned an empty text."}, status=502)

        return JsonResponse({"text": generated_text})

    def article_extra_fields_form(self, obj):
        return format_html(
            '<div class="article-extra-fields-form" data-empty-message="{}"></div>',
            _("Select a category with an article template to configure extra fields."),
        )

    article_extra_fields_form.short_description = _("Article extra fields")

    def article_content_images_manager(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<div class="article-content-images-config" data-url="" '
                'data-unsaved-message="{}"></div>',
                _("Save the article before uploading content images."),
            )

        return format_html(
            '<div class="article-content-images-config" data-url="{}" '
            'data-unsaved-message="{}"></div>',
            reverse(
                "admin:blog_manager_article_content_images",
                args=[obj.pk],
            ),
            _("Save the article before uploading content images."),
        )

    article_content_images_manager.short_description = _("Content images")

    def content_images_view(self, request, object_id):
        article = self.get_object(request, str(object_id))
        if not article:
            return JsonResponse({"error": _("Article not found.")}, status=404)
        if not self.has_change_permission(request, article):
            return JsonResponse({"error": _("Permission denied.")}, status=403)

        if request.method == "POST":
            action = request.POST.get("action", "upload")

            if action in {"update", "delete"}:
                image = ArticleImage.objects.filter(
                    pk=request.POST.get("image_id"),
                    article=article,
                ).first()
                if not image:
                    return JsonResponse(
                        {"error": _("Image not found.")},
                        status=404,
                    )

                if action == "delete":
                    image.delete()
                else:
                    image.alt_text = str(request.POST.get("alt") or "").strip()[:250]
                    try:
                        image.sort_order = max(
                            0,
                            int(request.POST.get("sort_order") or 0),
                        )
                    except (TypeError, ValueError):
                        image.sort_order = 0
                    image.save(update_fields=(
                        "alt_text",
                        "sort_order",
                        "updated_at",
                    ))

            elif action == "upload":
                uploads = request.FILES.getlist("images")
                if not uploads:
                    return JsonResponse(
                        {"error": _("Select at least one image.")},
                        status=400,
                    )

                existing_manifest = []
                for existing_image in article.content_images.all():
                    try:
                        size = existing_image.image.size
                    except (FileNotFoundError, OSError, ValueError):
                        size = 0
                    existing_manifest.append({"size": size})

                try:
                    validate_image_uploads(uploads, existing_manifest)
                except ValidationError as error:
                    return JsonResponse(
                        {"error": " ".join(error.messages)},
                        status=400,
                    )

                next_order = (
                    article.content_images
                    .order_by("-sort_order", "-pk")
                    .values_list("sort_order", flat=True)
                    .first()
                    or 0
                )
                created_images = []
                try:
                    for index, uploaded_file in enumerate(uploads, start=1):
                        alt_text = (
                            Path(uploaded_file.name).stem
                            .replace("-", " ")
                            .replace("_", " ")
                            .strip()
                        )
                        created_images.append(ArticleImage.objects.create(
                            article=article,
                            image=uploaded_file,
                            alt_text=alt_text[:250],
                            sort_order=next_order + index,
                        ))
                except Exception:
                    for created_image in created_images:
                        created_image.delete()
                    raise
            else:
                return JsonResponse(
                    {"error": _("Unsupported action.")},
                    status=400,
                )

        elif request.method != "GET":
            return JsonResponse(
                {"error": _("Unsupported request method.")},
                status=405,
            )

        images = article.content_images.all()
        return JsonResponse({
            "images": [article_image_payload(image) for image in images],
            "upload_help": _(
                "JPEG, PNG, WebP or AVIF; up to 25 MB per file. "
                "Files are saved only as AVIF with a maximum width of 1200 px."
            ),
        })

    def extra_fields_schema_view(self, request):
        if not self.has_view_or_change_permission(request):
            return JsonResponse({"error": "Permission denied."}, status=403)

        category = (
            Category.objects
            .select_related("article_theme_template")
            .filter(pk=request.GET.get("category_id"))
            .first()
        )

        if not category or not category.article_theme_template_id:
            return JsonResponse({"fields": []})

        schema = normalize_article_extra_fields_schema(
            category.article_theme_template.article_extra_fields_schema
        )

        return JsonResponse({"fields": list(schema.values())})

    def save_model(self, request, obj, form, change):
        if not obj.author_id and request.user.is_authenticated:
            obj.author = request.user

        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "theme_template":
            kwargs["queryset"] = ThemeTemplate.objects.filter(
                theme__is_active=True,
                template_type=TemplateType.CHILDREN_ARTICLE,
                is_active=True,
            )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )



@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = (
        "title",
        "slug",
        "created",
        "updated",
    )
    search_fields = (
        "title",
        "slug",
    )
    prepopulated_fields = {
        "slug": ("title",),
    }
    readonly_fields = (
        "created",
        "updated",
    )
