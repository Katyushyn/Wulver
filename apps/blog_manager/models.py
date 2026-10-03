import uuid
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from unidecode import unidecode

from .mixins import ImageProcessingMixin


def article_content_image_upload_to(instance, filename):
    extension = Path(filename).suffix.lower() or ".image"
    return (
        f"post/content/{instance.article_id}/"
        f"{uuid.uuid4().hex}{extension}"
    )


class BlogSettings(models.Model):
    default_category_template = models.ForeignKey(
        "theme_manager.ThemeTemplate",
        verbose_name=_("Default first category page template"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_blog_category_settings",
    )
    default_paginated_category_template = models.ForeignKey(
        "theme_manager.ThemeTemplate",
        verbose_name=_("Default paginated category template"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_paginated_blog_category_settings",
    )
    default_article_template = models.ForeignKey(
        "theme_manager.ThemeTemplate",
        verbose_name=_("Default article template"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_blog_article_settings",
    )
    default_category_schema_graph = models.JSONField(
        _("Default category schema graph"),
        blank=True,
        default=dict,
        help_text=_(
            "Optional JSON-LD graph used when a blog category has no custom schema."
        ),
    )
    default_article_schema_graph = models.JSONField(
        _("Default article schema graph"),
        blank=True,
        default=dict,
        help_text=_(
            "Optional JSON-LD graph used when a blog article has no custom schema."
        ),
    )

    class Meta:
        verbose_name = _("Blog settings")
        verbose_name_plural = _("Blog settings")

    def __str__(self):
        return str(_("Blog settings"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class LatestArticlesModule(models.Model):
    class Ordering(models.TextChoices):
        NEWEST = "newest", _("Newest first")
        OLDEST = "oldest", _("Oldest first")
        TITLE = "title", _("Title A-Z")

    name = models.CharField(_("Module name"), max_length=150)
    slug = models.SlugField(_("Slug"), max_length=150, unique=True)
    categories = models.ManyToManyField(
        "blog_manager.Category",
        related_name="latest_articles_modules",
        verbose_name=_("Categories"),
    )
    include_descendants = models.BooleanField(
        _("Include descendant categories"),
        default=True,
    )
    articles_count = models.PositiveIntegerField(
        _("Articles count"),
        default=5,
        validators=[MinValueValidator(1)],
    )
    ordering = models.CharField(
        _("Ordering"),
        max_length=20,
        choices=Ordering.choices,
        default=Ordering.NEWEST,
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Modules — Latest articles")
        verbose_name_plural = _("Modules — Latest articles")
        ordering = ("name", "pk")

    def __str__(self):
        return self.name


class TagModule(models.Model):
    class Source(models.TextChoices):
        CURRENT_ARTICLE = "current_article", _("Current article tags")
        CURRENT_CATEGORY = "current_category", _("Current category tags")
        GLOBAL_CLOUD = "global_cloud", _("Global tag cloud")

    class Ordering(models.TextChoices):
        TITLE = "title", _("Title A-Z")
        POPULARITY = "popularity", _("Most used first")

    class ClassMode(models.TextChoices):
        SEQUENTIAL = "sequential", _("One class per tag, in order")
        ALL = "all", _("All classes on every tag")
        RANDOM = "random", _("One random class per tag")

    name = models.CharField(_("Module name"), max_length=150)
    slug = models.SlugField(_("Slug"), max_length=150, unique=True)
    source = models.CharField(
        _("Tag source"),
        max_length=30,
        choices=Source.choices,
        default=Source.CURRENT_ARTICLE,
    )
    tags_count = models.PositiveIntegerField(
        _("Tags count"),
        default=21,
        validators=[MinValueValidator(1)],
        help_text=_("Maximum number of tags displayed by this module."),
    )
    ordering = models.CharField(
        _("Ordering"),
        max_length=20,
        choices=Ordering.choices,
        default=Ordering.TITLE,
    )
    classes = models.CharField(
        _("CSS classes"),
        max_length=1000,
        blank=True,
        help_text=_(
            "Enter CSS classes separated by commas, for example: "
            "badge-dark, badge-info, badge-success. Each item may contain several "
            "classes. Leave empty to add no classes."
        ),
    )
    class_mode = models.CharField(
        _("Class application"),
        max_length=20,
        choices=ClassMode.choices,
        default=ClassMode.SEQUENTIAL,
        help_text=_(
            "Choose whether classes are assigned in order, added all together, "
            "or selected randomly one per tag."
        ),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Modules — Tags")
        verbose_name_plural = _("Modules — Tags")
        ordering = ("name", "pk")

    def __str__(self):
        return self.name

    def parsed_classes(self):
        return [
            css_class.strip()
            for css_class in self.classes.split(",")
            if css_class.strip()
        ]


class ImageModule(models.Model):
    class DisplayMode(models.TextChoices):
        ALL = "all", _("All images")
        RANDOM_ONE = "random_one", _("One random image")
        SEQUENTIAL_ONE = "sequential_one", _("One image in daily rotation")
        ORDERED_COUNT = "ordered_count", _("Specified number in order")
        RANDOM_COUNT = "random_count", _("Specified number at random")

    name = models.CharField(_("Module name"), max_length=150)
    slug = models.SlugField(_("Slug"), max_length=150, unique=True)
    storage_key = models.UUIDField(
        _("Storage key"),
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    display_mode = models.CharField(
        _("Display mode"),
        max_length=30,
        choices=DisplayMode.choices,
        default=DisplayMode.RANDOM_ONE,
    )
    images_count = models.PositiveIntegerField(
        _("Images count"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text=_(
            "Used by modes that display a specified number of images."
        ),
    )
    manifest = models.JSONField(
        _("Manifest"), default=list, blank=True, editable=False
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Modules — Images")
        verbose_name_plural = _("Modules — Images")
        ordering = ("name", "pk")

    def __str__(self):
        return self.name

    @property
    def storage_prefix(self):
        return f"image_modules/{self.storage_key}"

    @property
    def active_manifest(self):
        return [item for item in self.manifest if item.get("active", True)]

    @property
    def storage_size(self):
        return sum(
            int(item.get("size") or 0)
            for item in self.manifest
        )


class Category(models.Model, ImageProcessingMixin):
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        null=True,
        blank=True,
        verbose_name=_("Parent category"),
    )
    title = models.CharField(max_length=250, verbose_name=_("Title"))
    noindex = models.BooleanField(_("Noindex"), default=False)
    slug = models.SlugField(
        max_length=250,
        unique=True,
        blank=True,
        verbose_name=_("Slug"),
    )
    description = models.TextField(
        verbose_name=_("Description"),
    )
    intro = models.TextField(blank=True, verbose_name=_("Intro"))
    keywords = models.CharField(
        _("Keywords"),
        max_length=255,
        blank=True,
        help_text=_("Comma-separated keywords."),
    )
    preview_image = models.ImageField(
        _("Preview image"),
        upload_to="category/previews/%Y/%m/",
        blank=True,
        null=True,
    )
    og_type = models.CharField(_("OG type"), max_length=100, blank=True)
    schema_graph = models.JSONField(
        _("Schema graph"),
        blank=True,
        default=dict,
        help_text=_("Optional JSON-LD graph for this category."),
    )
    canonical_allowed_params = models.CharField(
        _("Canonical allowed params"),
        max_length=255,
        blank=True,
        help_text=_(
            "Only the page parameter is supported. Page 1 is omitted from canonical URLs."
        ),
    )
    img = models.ImageField(
        upload_to="category/%Y/%m/",
        blank=True,
        verbose_name=_("Image"),
    )
    img_crop = models.ImageField(
        upload_to="category/%Y/%m/",
        editable=False,
        blank=True,
        verbose_name=_("Cropped image"),
    )
    img_crop_mob = models.ImageField(
        upload_to="category/%Y/%m/",
        editable=False,
        blank=True,
        verbose_name=_("Mobile cropped image"),
    )
    tags = models.ManyToManyField(
        "blog_manager.Tag",
        blank=True,
        verbose_name=_("Tags"),
    )
    theme_template = models.ForeignKey(
        "theme_manager.ThemeTemplate",
        verbose_name=_("First page template"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_categories",
    )
    paginated_theme_template = models.ForeignKey(
        "theme_manager.ThemeTemplate",
        verbose_name=_("Paginated pages template"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paginated_blog_categories",
        help_text=_("Used for category pages 2, 3, and later. If empty, first page template is used."),
    )
    article_theme_template = models.ForeignKey(
        "theme_manager.ThemeTemplate",
        verbose_name=_("Default article template"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="article_blog_categories",
        help_text=_("Used by articles in this category when the article has no custom template."),
    )
    icon = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        verbose_name=_("Icon"),
    )
    sort_order = models.PositiveIntegerField(
        _("Sort order"),
        default=0,
        blank=True,
    )
    articles_per_page = models.PositiveIntegerField(
        _("Articles per page"),
        default=5,
        validators=[MinValueValidator(1)],
        help_text=_("Number of articles displayed on each category page."),
    )
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("Updated"))

    class MPTTMeta:
        order_insertion_by = ["id"]

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ("parent__id", "sort_order", "id")

    def get_absolute_url(self):
        return reverse("blog:category", kwargs={"category_slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            self.slug = slugify(unidecode(self.title))
        if self.sort_order is None:
            self.sort_order = 0

        super().save(*args, **kwargs)
        self.handle_images("img", "img_crop", "img_crop_mob")

        if self.img:
            super().save(update_fields=["img_crop", "img_crop_mob"])

    def __str__(self):
        return self.title

    @classmethod
    def normalize_sort_order(cls):
        groups = {}

        categories = cls.objects.order_by(
            "parent_id",
            "sort_order",
            "id",
        )

        for category in categories:
            groups.setdefault(category.parent_id, []).append(category)

        for parent_id, group_categories in groups.items():
            for index, category in enumerate(group_categories, start=1):
                if category.sort_order != index:
                    category.sort_order = index
                    category.save(update_fields=["sort_order"])


class Article(models.Model, ImageProcessingMixin):
    STATUS_CHOICES = (
        ("standard", _("Standard")),
        ("top", _("Priority")),
    )

    title = models.CharField(max_length=250, verbose_name=_("Title"))
    noindex = models.BooleanField(_("Noindex"), default=False)
    slug = models.SlugField(max_length=250, unique=True, verbose_name=_("Slug"))
    description = models.TextField(
        verbose_name=_("Description"),
    )
    keywords = models.CharField(
        _("Keywords"),
        max_length=255,
        blank=True,
        help_text=_("Comma-separated keywords."),
    )
    preview_image = models.ImageField(
        _("Preview image"),
        upload_to="post/previews/%Y/%m/",
        blank=True,
        null=True,
    )
    og_type = models.CharField(_("OG type"), max_length=100, blank=True)
    schema_graph = models.JSONField(
        _("Schema graph"),
        blank=True,
        default=dict,
        help_text=_("Optional JSON-LD graph for this article."),
    )
    canonical_allowed_params = models.CharField(
        _("Canonical allowed params"),
        max_length=255,
        blank=True,
        help_text=_(
            "Only the page parameter is supported. Page 1 is omitted from canonical URLs."
        ),
    )
    article_extra_fields = models.JSONField(
        _("Article extra fields"),
        blank=True,
        default=dict,
        help_text=_("Values for extra fields defined by the category article template."),
    )
    author = models.ForeignKey(
        User,
        editable=False,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        verbose_name=_("Author"),
    )
    category = models.ForeignKey(
        "blog_manager.Category",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Category"),
    )
    theme_template = models.ForeignKey(
        "theme_manager.ThemeTemplate",
        verbose_name=_("Template"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_articles",
    )
    img = models.ImageField(
        upload_to="post/%Y/%m/",
        null=True,
        blank=True,
        verbose_name=_("Image"),
    )
    img_crop = models.ImageField(
        upload_to="post/%Y/%m/",
        editable=False,
        blank=True,
        verbose_name=_("Cropped image"),
    )
    img_crop_mob = models.ImageField(
        upload_to="post/%Y/%m/",
        editable=False,
        blank=True,
        verbose_name=_("Mobile cropped image"),
    )
    intro = models.TextField(verbose_name=_("Intro"))
    body = models.TextField(verbose_name=_("Article body"))
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="standard",
        verbose_name=_("Status"),
    )
    tags = models.ManyToManyField(
        "blog_manager.Tag",
        blank=True,
        verbose_name=_("Tags"),
    )
    is_published = models.BooleanField(default=True, verbose_name=_("Published"))
    publish = models.DateTimeField(default=timezone.now, verbose_name=_("Publish date"))
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("Updated"))

    class Meta:
        verbose_name = _("Article")
        verbose_name_plural = _("Articles")
        ordering = ("-publish",)

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            self.slug = slugify(unidecode(self.title))

        super().save(*args, **kwargs)
        self.handle_images("img", "img_crop", "img_crop_mob")

        if self.img:
            super().save(update_fields=["img", "img_crop", "img_crop_mob"])

    def get_absolute_url(self):
        return reverse(
            "blog:post",
            kwargs={"category_slug": self.category.slug, "post_slug": self.slug},
        )

    def __str__(self):
        return self.title


class ArticleImage(models.Model, ImageProcessingMixin):
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="content_images",
        verbose_name=_("Article"),
    )
    image = models.ImageField(
        _("Image"),
        upload_to=article_content_image_upload_to,
    )
    alt_text = models.CharField(
        _("Alt text"),
        max_length=250,
        blank=True,
        help_text=_("Describe the image for accessibility and search engines."),
    )
    width = models.PositiveIntegerField(_("Width"), editable=False, default=0)
    height = models.PositiveIntegerField(_("Height"), editable=False, default=0)
    sort_order = models.PositiveIntegerField(_("Sort order"), default=0)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Article image")
        verbose_name_plural = _("Article images")
        ordering = ("sort_order", "pk")

    def __str__(self):
        return self.alt_text or Path(self.image.name).name

    def save(self, *args, **kwargs):
        previous_name = ""
        if self.pk:
            previous_name = (
                type(self).objects
                .filter(pk=self.pk)
                .values_list("image", flat=True)
                .first()
                or ""
            )

        current_name = self.image.name if self.image else ""
        image_changed = bool(self.image and current_name != previous_name)
        super().save(*args, **kwargs)

        if not image_changed:
            return

        dimensions = self.handle_content_image("image", max_width=1200)
        if dimensions:
            self.width, self.height = dimensions
            type(self).objects.filter(pk=self.pk).update(
                image=self.image.name,
                width=self.width,
                height=self.height,
            )

        if previous_name and previous_name != self.image.name:
            default_storage.delete(previous_name)

class Tag(models.Model):
    title = models.CharField(max_length=250, verbose_name=_("Tag"))
    slug = models.SlugField(max_length=250, unique=True, verbose_name=_("Slug"))
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("Updated"))

    class Meta:
        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")
        ordering = ["id"]

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            self.slug = slugify(unidecode(self.title))

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
