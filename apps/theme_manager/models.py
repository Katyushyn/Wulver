from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import shutil
from pathlib import Path
from django.conf import settings


class Theme(models.Model):
    name = models.CharField(_("Name"), max_length=150)
    slug = models.SlugField(_("Slug"), unique=True)
    description = models.TextField(_("Description"), blank=True)

    preview_image = models.ImageField(
        _("Preview image"),
        upload_to="themes/previews/",
        blank=True,
        null=True,
    )

    templates_map = models.JSONField(
        _("Templates map"),
        default=dict,
        blank=True,
    )

    is_active = models.BooleanField(_("Active"), default=False)

    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Theme")
        verbose_name_plural = _("Themes")
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if self.is_active:
            self.__class__.objects.exclude(
                pk=self.pk,
            ).update(
                is_active=False,
            )

        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        return cls.objects.filter(
            is_active=True,
        ).first()

    def delete(self, *args, **kwargs):
        theme_slug = self.slug

        result = super().delete(*args, **kwargs)

        static_dir = (
                Path(settings.BASE_DIR)
                / "static"
                / "themes"
                / theme_slug
        )

        template_dir = (
                Path(settings.BASE_DIR)
                / "templates"
                / theme_slug
        )

        if static_dir.exists():
            shutil.rmtree(static_dir)

        if template_dir.exists():
            shutil.rmtree(template_dir)

        return result

    def __str__(self):
        return self.name


class TemplateType(models.TextChoices):
    BASE_TEMPLATE = "base_template", _("Base Template")
    INCLUDE_BLOCK = "include_block", _("-- Include block")
    PARENT_PAGE = "parent_page", _("-- Parent Page")
    PARENT_BLOG = "parent_blog", _("-- Parent Blog")
    PARENT_ARTICLE = "parent_article", _("-- Parent Article")
    SEARCH_PAGE = "search_page", _("-- Search Page")
    ERROR_TEMPLATE = "error_template", _("Error Page")


class ThemeTemplate(models.Model):
    theme = models.ForeignKey(
        Theme,
        on_delete=models.CASCADE,
        related_name="templates",
        verbose_name=_("Theme"),
    )

    template_type = models.CharField(
        _("Template type"),
        max_length=30,
        choices=TemplateType.choices,
    )

    name = models.CharField(_("Name"), max_length=150)
    slug = models.SlugField(_("Slug"))

    article_extra_fields_schema = models.JSONField(
        _("Article extra fields schema"),
        blank=True,
        default=dict,
        help_text=_(
            "JSON schema for extra article fields used by categories with this article template."
        ),
    )

    css_classes = models.JSONField(
        default=list,
        blank=True,
        editable=False,
    )

    is_active = models.BooleanField(_("Active"), default=True)

    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Template")
        verbose_name_plural = _("Templates")
        unique_together = ("theme", "slug")
        ordering = ["theme", "template_type", "name"]

    def save(self, *args, **kwargs):
        if self.theme_id and not Theme.objects.filter(is_active=True).exists():
            self.theme.is_active = True
            self.theme.save(update_fields=["is_active"])

        if self.theme_id and self.template_type:
            active_templates = self.__class__.objects.filter(
                theme_id=self.theme_id,
                template_type=self.template_type,
                is_active=True,
            )

            if self.pk:
                active_templates = active_templates.exclude(pk=self.pk)

            if not active_templates.exists():
                self.is_active = True

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.theme} / {self.name}"


class ThemeTemplateVersion(models.Model):
    template = models.ForeignKey(
        ThemeTemplate,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name=_("Template"),
    )
    code = models.TextField(_("Code"))
    code_hash = models.CharField(_("Code hash"), max_length=64)
    line_count = models.PositiveIntegerField(_("Line count"), default=0)
    source = models.CharField(_("Source"), max_length=40, default="save")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="theme_template_versions",
        verbose_name=_("Created by"),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("Template version")
        verbose_name_plural = _("Template versions")
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(
                fields=["template", "-created_at"],
                name="theme_ver_template_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.template} / {self.created_at:%Y-%m-%d %H:%M:%S}"


class TemplateComponent(models.Model):
    name = models.CharField(_("Component name"), max_length=150)
    slug = models.SlugField(_("Slug"), unique=True)
    category = models.CharField(_("Category"), max_length=100)
    icon = models.CharField(_("Icon"), max_length=80, default="view_cozy")
    description = models.TextField(_("Description"), blank=True)
    code = models.TextField(_("Code"))
    ai_conversion_prompt = models.TextField(_("AI conversion prompt"), blank=True)
    latest_articles_modules = models.ManyToManyField(
        "blog_manager.LatestArticlesModule",
        blank=True,
        related_name="template_components",
        verbose_name=_("Modules — Latest articles"),
        help_text=_(
            "Available configurations for the Latest blog articles component."
        ),
    )
    tag_modules = models.ManyToManyField(
        "blog_manager.TagModule",
        blank=True,
        related_name="template_components",
        verbose_name=_("Modules — Tags"),
        help_text=_("Available configurations for the Tags component."),
    )
    image_modules = models.ManyToManyField(
        "blog_manager.ImageModule",
        blank=True,
        related_name="template_components",
        verbose_name=_("Modules — Images"),
        help_text=_("Available configurations for the Images component."),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    sort_order = models.PositiveIntegerField(_("Sort order"), default=0)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Template component")
        verbose_name_plural = _("Template components")
        ordering = ["category", "sort_order", "name"]

    def __str__(self):
        return self.name
