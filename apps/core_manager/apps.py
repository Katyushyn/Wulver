from django.apps import AppConfig


class CoreManagerConfig(AppConfig):
    name = "apps.core_manager"

    def ready(self):
        from .admin_help import install_admin_help_templates
        from . import redirect_signals  # noqa: F401
        from . import sitemap_signals  # noqa: F401

        install_admin_help_templates()
