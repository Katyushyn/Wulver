from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CommentsManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.comments_manager"
    verbose_name = _("Comments manager")

    def ready(self):
        from . import signals  # noqa: F401
