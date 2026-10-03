import shutil
from pathlib import Path

from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Theme, ThemeTemplate


@receiver(post_delete, sender=ThemeTemplate)
def delete_theme_template_file(sender, instance, **kwargs):
    if not instance.theme_id or not instance.slug:
        return

    template_file = (
        Path(settings.BASE_DIR)
        / "templates"
        / instance.theme.slug
        / f"{instance.slug}.html"
    )
    if template_file.is_file():
        template_file.unlink()


@receiver(post_delete, sender=Theme)
def delete_theme_directories(sender, instance, **kwargs):
    static_dir = (
        Path(settings.BASE_DIR)
        / "static"
        / "themes"
        / instance.slug
    )

    template_dir = (
        Path(settings.BASE_DIR)
        / "templates"
        / instance.slug
    )

    if static_dir.exists():
        shutil.rmtree(static_dir)

    if template_dir.exists():
        shutil.rmtree(template_dir)
