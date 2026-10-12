from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from urllib.parse import urlsplit


class DashboardReadState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    model_label = models.CharField(max_length=100)
    seen_until = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=('user', 'model_label'), name='dashboard_read_state_unique')]


class SiteSettings(models.Model):
    site_name = models.CharField(_("Site name"), max_length=255, default="Wulver")
    site_domain = models.CharField(
        _("Site domain"),
        max_length=255,
        blank=True,
        help_text=_("Public domain without protocol, for example: example.com."),
    )
    site_url = models.URLField(
        _("Site URL"),
        blank=True,
        help_text=_("Public URL with protocol, for example: https://example.com."),
    )
    contact_email = models.EmailField(_("Contact email"), blank=True)
    contact_phone = models.CharField(_("Contact phone"), max_length=100, blank=True)
    newsletter_require_confirmation = models.BooleanField(
        _("Newsletter email confirmation"),
        default=True,
        help_text=_("Require subscribers to confirm their address by email."),
    )
    newsletter_rate_limit = models.PositiveIntegerField(
        _("Newsletter requests per window"), default=3
    )
    newsletter_rate_window = models.PositiveIntegerField(
        _("Newsletter rate window (seconds)"), default=600
    )
    newsletter_confirmation_rate_limit = models.PositiveIntegerField(
        _("Confirmation emails per window"), default=3
    )
    newsletter_confirmation_rate_window = models.PositiveIntegerField(
        _("Confirmation email window (seconds)"), default=3600
    )
    newsletter_confirmation_token_ttl = models.PositiveIntegerField(
        _("Confirmation link lifetime (seconds)"), default=86400
    )
    contact_rate_limit = models.PositiveIntegerField(
        _("Contact messages per window"), default=5
    )
    contact_rate_window = models.PositiveIntegerField(
        _("Contact rate window (seconds)"), default=600
    )
    contact_message_max_length = models.PositiveIntegerField(
        _("Contact message maximum length"), default=10000
    )
    error_404_template = models.ForeignKey(
        "theme_manager.ThemeTemplate",
        verbose_name=_("404 error template"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="site_settings_404",
    )
    search_template = models.ForeignKey(
        "theme_manager.ThemeTemplate",
        verbose_name=_("Search template"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="site_settings_search",
        help_text=_("Rendered at /search/ for article search results."),
    )
    home_page = models.ForeignKey(
        "core_manager.Page",
        verbose_name=_("Home page"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="site_settings_home",
        help_text=_("Rendered at the site root URL."),
    )
    reviews_enabled = models.BooleanField(
        _("Reviews enabled"),
        default=True,
    )
    reviews_limit = models.PositiveIntegerField(
        _("Reviews limit"),
        default=10,
        help_text=_("Maximum number of external reviews shown on the site."),
    )
    reviews_cache_timeout = models.PositiveIntegerField(
        _("Reviews cache timeout"),
        default=1800,
        help_text=_("External reviews cache lifetime in seconds."),
    )
    github_reviews_enabled = models.BooleanField(
        _("GitHub reviews enabled"),
        default=False,
    )
    github_reviews_repository = models.CharField(
        _("GitHub reviews repository"),
        max_length=255,
        default="",
        blank=True,
        help_text=_("Repository in owner/name format."),
    )
    github_reviews_issue_number = models.PositiveIntegerField(
        _("GitHub reviews issue number"),
        blank=True,
        null=True,
        help_text=_("Issue number whose comments are used as reviews."),
    )
    github_reviews_timeout = models.PositiveIntegerField(
        _("GitHub reviews timeout"),
        default=5,
        help_text=_("GitHub API timeout in seconds."),
    )

    title = models.CharField(
        _("Title"),
        max_length=255,
        blank=True,
    )
    description = models.TextField(
        _("Description"),
        blank=True,
    )
    default_preview_image = models.ImageField(
        _("Default preview image"),
        upload_to="core/settings/previews/",
        blank=True,
        null=True,
    )
    default_image_alt = models.CharField(
        _("Default image alt"),
        max_length=255,
        blank=True,
    )
    theme_color = models.CharField(
        _("Theme color"),
        max_length=32,
        default="#ffffff",
    )
    robots_txt = models.TextField(
        _("Robots.txt"),
        blank=True,
        help_text=_("Optional robots.txt content managed from the admin."),
    )

    favicon_ico = models.FileField(
        _("Favicon ICO"),
        upload_to="core/settings/favicons/",
        blank=True,
        null=True,
    )
    favicon_png = models.ImageField(
        _("Favicon PNG"),
        upload_to="core/settings/favicons/",
        blank=True,
        null=True,
    )
    apple_touch_icon = models.ImageField(
        _("Apple touch icon"),
        upload_to="core/settings/favicons/",
        blank=True,
        null=True,
    )

    google_analytics_id = models.CharField(
        _("Google Analytics ID"),
        max_length=100,
        blank=True,
    )
    google_tag_manager_id = models.CharField(
        _("Google Tag Manager ID"),
        max_length=100,
        blank=True,
    )
    twitter_handle = models.CharField(_("Twitter handle"), max_length=100, blank=True)
    facebook_url = models.URLField(_("Facebook URL"), blank=True)
    instagram_url = models.URLField(_("Instagram URL"), blank=True)
    linkedin_url = models.URLField(_("LinkedIn URL"), blank=True)
    youtube_url = models.URLField(_("YouTube URL"), blank=True)
    tiktok_url = models.URLField(_("TikTok URL"), blank=True)
    telegram_url = models.URLField(_("Telegram URL"), blank=True)
    whatsapp_url = models.URLField(_("WhatsApp URL"), blank=True)
    x_url = models.URLField(_("X URL"), blank=True)

    author_name = models.CharField(_("Author name"), max_length=255, blank=True)
    og_site_name = models.CharField(_("OG site name"), max_length=255, blank=True)
    default_og_type = models.CharField(
        _("Default OG type"),
        max_length=100,
        default="website",
        blank=True,
    )

    organization_name = models.CharField(
        _("Organization name"),
        max_length=255,
        blank=True,
    )
    person_name = models.CharField(_("Person name"), max_length=255, blank=True)
    person_job_title = models.CharField(_("Person job title"), max_length=255, blank=True)
    same_as_links = models.TextField(
        _("Same as links"),
        blank=True,
        help_text=_("One social/profile URL per line for schema.org sameAs."),
    )
    organization_logo = models.ImageField(
        _("Organization logo"),
        upload_to="core/settings/schema/organization/",
        blank=True,
        null=True,
    )
    person_image = models.ImageField(
        _("Person image"),
        upload_to="core/settings/schema/person/",
        blank=True,
        null=True,
    )
    default_schema_graph = models.JSONField(
        _("Default schema graph"),
        blank=True,
        default=dict,
        help_text=_("Optional JSON-LD graph override used when a page has no custom schema."),
    )
    canonical_allowed_params = models.CharField(
        _("Canonical allowed params"),
        max_length=255,
        default="page",
        blank=True,
        help_text=_(
            "Only the page parameter is supported. Page 1 is omitted from canonical URLs."
        ),
    )

    maintenance_mode = models.BooleanField(_("Maintenance mode"), default=False)
    maintenance_message = models.TextField(_("Maintenance message"), blank=True)

    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Site settings")
        verbose_name_plural = _("Site settings")

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class SitemapSettings(models.Model):
    enabled = models.BooleanField(_("Enable sitemap"), default=True)
    include_homepage = models.BooleanField(_("Include homepage"), default=True)
    include_pages = models.BooleanField(_("Include pages"), default=True)
    include_categories = models.BooleanField(_("Include blog categories"), default=True)
    include_articles = models.BooleanField(_("Include articles"), default=True)
    include_translations = models.BooleanField(
        _("Include translated versions"),
        default=True,
        help_text=_("Include only language versions that contain translated content."),
    )
    include_alternates = models.BooleanField(
        _("Include alternate language links"),
        default=True,
        help_text=_("Add hreflang and x-default links to sitemap entries."),
    )
    homepage_priority = models.DecimalField(
        _("Homepage priority"),
        max_digits=2,
        decimal_places=1,
        default=1.0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    page_priority = models.DecimalField(
        _("Pages priority"),
        max_digits=2,
        decimal_places=1,
        default=0.8,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    category_priority = models.DecimalField(
        _("Categories priority"),
        max_digits=2,
        decimal_places=1,
        default=0.8,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    article_priority = models.DecimalField(
        _("Articles priority"),
        max_digits=2,
        decimal_places=1,
        default=0.7,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    cache_timeout = models.PositiveIntegerField(
        _("Cache lifetime (seconds)"),
        default=3600,
        help_text=_("Use 0 to disable sitemap response caching."),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Sitemap settings")
        verbose_name_plural = _("Sitemap settings")

    def __str__(self):
        return str(_("Sitemap settings"))

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class ContactMessage(models.Model):
    name = models.CharField(_("Name"), max_length=255)
    email = models.EmailField(_("Email"))
    subject = models.CharField(_("Subject"), max_length=255)
    message = models.TextField(_("Message"))
    source_url = models.URLField(_("Source URL"), max_length=1000, blank=True)
    ip_address = models.GenericIPAddressField(_("IP address"), blank=True, null=True)
    user_agent = models.TextField(_("User agent"), blank=True)
    is_read = models.BooleanField(_("Read"), default=False)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} <{self.email}>"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()

        super().save(*args, **kwargs)


class NewsletterSubscription(models.Model):
    email = models.EmailField(_("Email"), unique=True)
    is_active = models.BooleanField(_("Active"), default=True)
    source_url = models.URLField(_("Source URL"), max_length=1000, blank=True)
    ip_address = models.GenericIPAddressField(_("IP address"), blank=True, null=True)
    user_agent = models.TextField(_("User agent"), blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")
        ordering = ("-created_at",)

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()

        super().save(*args, **kwargs)


class Page(models.Model):
    seo_title = models.CharField(_("SEO title"), max_length=250, blank=True)
    title = models.CharField(_("Title"), max_length=255)
    slug = models.SlugField(
        max_length=250,
        unique=True,
        blank=True,
        verbose_name=_("Slug"),
    )

    template = models.OneToOneField(
        "theme_manager.ThemeTemplate",
        verbose_name=_("Template"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page",
    )

    is_published = models.BooleanField(_("Published"), default=True)
    noindex = models.BooleanField(_("Noindex"), default=False)

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
        upload_to="core/pages/previews/",
        blank=True,
        null=True,
    )
    og_type = models.CharField(_("OG type"), max_length=100, blank=True)
    schema_graph = models.JSONField(
        _("Schema graph"),
        blank=True,
        default=dict,
        help_text=_("Optional JSON-LD graph for this page."),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")
        ordering = ("title",)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        settings = SiteSettings.get_solo()
        if settings.home_page_id == self.pk:
            return reverse("core_manager:home")

        return reverse("core_manager:slug_detail", kwargs={"slug": self.slug})


class URLLink(models.Model):
    title = models.CharField(_("Title"), max_length=255)
    url = models.CharField(_("URL"), max_length=500)

    open_in_new_tab = models.BooleanField(_("Open in new tab"), default=False)
    nofollow = models.BooleanField(_("Nofollow"), default=False)

    css_class = models.CharField(_("CSS class"), max_length=255, blank=True)
    icon = models.CharField(_("Icon"), max_length=100, blank=True)

    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("URL link")
        verbose_name_plural = _("URL links")
        ordering = ("title",)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.url


class URLRedirect(models.Model):
    STATUS_PERMANENT = 301
    STATUS_TEMPORARY = 302
    STATUS_CHOICES = (
        (STATUS_PERMANENT, _("301 — Permanent")),
        (STATUS_TEMPORARY, _("302 — Temporary")),
    )

    old_path = models.CharField(
        _("Old path"),
        max_length=1000,
        unique=True,
        help_text=_("Local path beginning with /, without a domain or query string."),
    )
    target_url = models.CharField(
        _("Target URL"),
        max_length=1000,
        help_text=_("A local path beginning with / or a complete external URL."),
    )
    status_code = models.PositiveSmallIntegerField(
        _("Redirect type"),
        choices=STATUS_CHOICES,
        default=STATUS_PERMANENT,
    )
    is_active = models.BooleanField(_("Active"), default=True)
    is_automatic = models.BooleanField(
        _("Created automatically"),
        default=False,
        editable=False,
    )
    hit_count = models.PositiveBigIntegerField(_("Hits"), default=0, editable=False)
    last_used_at = models.DateTimeField(_("Last used at"), blank=True, null=True, editable=False)
    note = models.CharField(_("Note"), max_length=255, blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("URL redirect")
        verbose_name_plural = _("URL redirects")
        ordering = ("old_path",)

    def __str__(self):
        return f"{self.old_path} → {self.target_url}"

    @staticmethod
    def normalize_old_path(value):
        value = str(value or "").strip()
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            raise ValidationError(_("Old path must be local and must not contain a domain."))
        if parsed.query or parsed.fragment:
            raise ValidationError(_("Old path must not contain a query string or fragment."))
        path = parsed.path or "/"
        return path if path.startswith("/") else "/" + path

    @staticmethod
    def normalize_target_url(value):
        value = str(value or "").strip()
        if not value:
            raise ValidationError(_("Target URL is required."))
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValidationError(_("External target must be a complete HTTP or HTTPS URL."))
            return value
        return value if value.startswith("/") else "/" + value

    def clean(self):
        super().clean()
        self.old_path = self.normalize_old_path(self.old_path)
        self.target_url = self.normalize_target_url(self.target_url)
        if self.target_url == self.old_path:
            raise ValidationError({"target_url": _("A URL cannot redirect to itself.")})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
