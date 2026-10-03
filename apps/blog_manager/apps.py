from django.apps import AppConfig


class BlogManagerConfig(AppConfig):
    name = "apps.blog_manager"

    def ready(self):
        from . import signals  # noqa: F401
