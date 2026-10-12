from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AnalyticsManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics_manager"
    verbose_name = _("Analytics manager")

