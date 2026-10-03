from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BackupManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.backup_manager"
    verbose_name = _("Backup manager")
