from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.cache import cache
from django.db import models
from django.utils.translation import gettext_lazy as _


class AnalyticsSettings(models.Model):
    class CollectionMode(models.TextChoices):
        COMPACT = "compact", _("Compact — daily totals only")
        DETAILED = "detailed", _("Detailed — record every visit")

    class IPStorageMode(models.TextChoices):
        NONE = "none", _("Do not store")
        MASKED = "masked", _("Store masked address")
        HASHED = "hashed", _("Store irreversible hash")
        FULL = "full", _("Store full address")

    enabled = models.BooleanField(_("Analytics enabled"), default=True)
    collection_mode = models.CharField(
        _("Collection mode"),
        max_length=10,
        choices=CollectionMode.choices,
        default=CollectionMode.COMPACT,
        help_text=_(
            "Compact mode stores only daily totals. Detailed mode additionally "
            "stores every page view for the configured retention period."
        ),
    )
    ip_storage_mode = models.CharField(
        _("IP address storage"),
        max_length=10,
        choices=IPStorageMode.choices,
        default=IPStorageMode.HASHED,
        help_text=_(
            "Hashed mode can count returning visitors without retaining their address."
        ),
    )
    retention_days = models.PositiveIntegerField(
        _("Detailed visit retention (days)"),
        default=90,
        validators=[MinValueValidator(1)],
        help_text=_("Daily totals are preserved when old detailed visits are removed."),
    )
    exclude_staff = models.BooleanField(
        _("Exclude staff users"),
        default=True,
    )
    exclude_bots = models.BooleanField(
        _("Exclude known bots"),
        default=True,
    )
    record_query_string = models.BooleanField(
        _("Record query parameters"),
        default=True,
        help_text=_("Sensitive parameter values are always replaced with [redacted]."),
    )
    excluded_path_prefixes = models.TextField(
        _("Excluded URL prefixes"),
        default=(
            "/admin/\n/static/\n/media/\n/rosetta/\n/ai-assistant/health/\n"
            "/favicon.ico\n/favicon.png\n/apple-touch-icon"
        ),
        blank=True,
        help_text=_("One local URL prefix per line."),
    )
    sensitive_query_parameters = models.TextField(
        _("Sensitive query parameters"),
        default=(
            "password\npasswd\npass\ntoken\naccess_token\nrefresh_token\n"
            "api_key\nkey\nsecret\ncode\nemail"
        ),
        blank=True,
        help_text=_("One parameter name per line. Values are never stored."),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Analytics settings")
        verbose_name_plural = _("Analytics settings")

    def __str__(self):
        return str(_("Analytics settings"))

    def save(self, *args, **kwargs):
        self.pk = 1
        result = super().save(*args, **kwargs)
        cache.delete("analytics:configuration")
        return result

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def excluded_prefixes(self):
        return tuple(
            line.strip() for line in self.excluded_path_prefixes.splitlines() if line.strip()
        )

    def sensitive_parameters(self):
        return {
            line.strip().casefold()
            for line in self.sensitive_query_parameters.splitlines()
            if line.strip()
        }


class Visit(models.Model):
    created_at = models.DateTimeField(_("Visited at"), auto_now_add=True, db_index=True)
    path = models.CharField(_("Path"), max_length=1000, db_index=True)
    query_string = models.TextField(_("Query parameters"), blank=True)
    method = models.CharField(_("Method"), max_length=10, default="GET")
    status_code = models.PositiveSmallIntegerField(_("Status code"), db_index=True)
    view_name = models.CharField(_("View"), max_length=255, blank=True, db_index=True)
    app_name = models.CharField(_("Application"), max_length=100, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("User"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="site_visits",
    )
    ip_address = models.GenericIPAddressField(
        _("IP address"), blank=True, null=True
    )
    ip_hash = models.CharField(_("IP hash"), max_length=64, blank=True, db_index=True)
    visitor_hash = models.CharField(
        _("Visitor hash"), max_length=64, blank=True, db_index=True
    )
    referrer = models.URLField(_("Referrer"), max_length=2000, blank=True)
    user_agent = models.CharField(_("User agent"), max_length=512, blank=True)

    class Meta:
        verbose_name = _("Visit")
        verbose_name_plural = _("Visits")
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("path", "created_at"), name="analytics_path_time_idx"),
        ]

    def __str__(self):
        return f"{self.path} — {self.created_at:%Y-%m-%d %H:%M:%S}"


class DailyPageStat(models.Model):
    date = models.DateField(_("Date"), db_index=True)
    path = models.CharField(_("Path"), max_length=1000)
    view_name = models.CharField(_("View"), max_length=255, blank=True)
    views = models.PositiveBigIntegerField(_("Views"), default=0)
    unique_visitors = models.PositiveBigIntegerField(_("Unique visitors"), default=0)

    class Meta:
        verbose_name = _("Daily page statistic")
        verbose_name_plural = _("Daily page statistics")
        ordering = ("-date", "-views", "path")
        constraints = [
            models.UniqueConstraint(
                fields=("date", "path"), name="analytics_unique_daily_page"
            )
        ]

    def __str__(self):
        return f"{self.date} — {self.path}"


class DailySiteStat(models.Model):
    date = models.DateField(_("Date"), unique=True)
    views = models.PositiveBigIntegerField(_("Views"), default=0)
    unique_visitors = models.PositiveBigIntegerField(_("Unique visitors"), default=0)

    class Meta:
        verbose_name = _("Daily site statistic")
        verbose_name_plural = _("Daily site statistics")
        ordering = ("-date",)

    def __str__(self):
        return str(self.date)


class DailyUniqueVisitor(models.Model):
    date = models.DateField()
    path = models.CharField(max_length=1000)
    visitor_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("date", "path", "visitor_hash"),
                name="analytics_unique_daily_visitor",
            )
        ]
        indexes = [
            models.Index(fields=("date", "path"), name="analytics_unique_day_idx"),
        ]

