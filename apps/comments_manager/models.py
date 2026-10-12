from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _


class LatestCommentsModule(models.Model):
    name = models.CharField(_("Module name"), max_length=150)
    slug = models.SlugField(_("Slug"), max_length=150, unique=True)
    categories = models.ManyToManyField("blog_manager.Category", verbose_name=_("Categories"))
    include_descendants = models.BooleanField(_("Include descendant categories"), default=True)
    comments_count = models.PositiveIntegerField(_("Comments count"), default=5, validators=[MinValueValidator(1)])
    per_article_limit = models.PositiveIntegerField(_("Maximum comments per article"), default=1, validators=[MinValueValidator(1)])
    excerpt_words = models.PositiveIntegerField(_("Comment excerpt words"), default=13, validators=[MinValueValidator(1)], help_text=_("Maximum words in the plain-text comment excerpt."))
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Modules — Latest comments")
        verbose_name_plural = _("Modules — Latest comments")
        ordering = ("name", "pk")

    def __str__(self):
        return self.name


class CommentSettings(models.Model):
    class PublicationMode(models.TextChoices):
        IMMEDIATE = "immediate", _("Publish immediately")
        MODERATION = "moderation", _("Send to moderation")

    allow_anonymous_comments = models.BooleanField(
        _("Allow comments from unauthenticated users"),
        default=False,
        help_text=_("When disabled, only signed-in users can submit comments."),
    )
    publication_mode = models.CharField(
        _("New comments"),
        max_length=20,
        choices=PublicationMode.choices,
        default=PublicationMode.IMMEDIATE,
    )
    rate_limit_count = models.PositiveIntegerField(
        _("Maximum comments"),
        default=3,
        validators=[MinValueValidator(1)],
    )
    rate_limit_window_minutes = models.PositiveIntegerField(
        _("Time window (minutes)"),
        default=10,
        validators=[MinValueValidator(1)],
        help_text=_("Limits comments per user and IP address during this period."),
    )
    form_title = models.CharField(_("Form title"), max_length=255)
    comment_label = models.CharField(_("Comment label"), max_length=150)
    comment_placeholder = models.CharField(_("Comment placeholder"), max_length=255)
    submit_text = models.CharField(_("Submit button text"), max_length=150)
    empty_text = models.CharField(_("Empty comments text"), max_length=255)
    stylesheet = models.TextField(
        _("Comments stylesheet"),
        help_text=_("CSS shared by all system comment templates."),
    )
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Comment appearance")
        verbose_name_plural = _("Comment appearance")

    def __str__(self):
        return str(_("Comment appearance"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def get_solo(cls):
        from .defaults import (
            DEFAULT_COMMENT_STYLESHEET,
            DEFAULT_COMMENT_TEXTS,
        )

        defaults = DEFAULT_COMMENT_TEXTS["en"] | {
            "stylesheet": DEFAULT_COMMENT_STYLESHEET,
        }
        obj, _created = cls.objects.get_or_create(pk=1, defaults=defaults)
        return obj


class CommentTemplate(models.Model):
    class TemplateType(models.TextChoices):
        FORM = "form", _("Comment form")
        LIST = "list", _("Comment list")
        COMMENT = "comment", _("Single comment")

    template_type = models.CharField(
        _("Comment template"),
        max_length=20,
        choices=TemplateType.choices,
        unique=True,
    )
    code = models.TextField(_("Template code"))
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Comment template")
        verbose_name_plural = _("Comment templates")
        ordering = ("template_type",)

    def __str__(self):
        return self.get_template_type_display()
