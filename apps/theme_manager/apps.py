from django.apps import AppConfig


class ThemeManagerConfig(AppConfig):
    name = "apps.theme_manager"

    def ready(self):
        from apps.theme_manager import signals  # noqa: F401
