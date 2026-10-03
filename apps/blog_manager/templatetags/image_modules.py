import random

from django import template
from django.utils import timezone

from apps.blog_manager.image_module_storage import manifest_with_urls
from apps.blog_manager.models import ImageModule


register = template.Library()


@register.simple_tag
def image_module(module_slug):
    module = ImageModule.objects.filter(slug=module_slug, is_active=True).first()
    if module is None:
        return []

    items = manifest_with_urls(module.active_manifest)
    if not items:
        return []

    if module.display_mode == ImageModule.DisplayMode.RANDOM_ONE:
        return [random.choice(items)]
    if module.display_mode == ImageModule.DisplayMode.SEQUENTIAL_ONE:
        index = timezone.localdate().toordinal() % len(items)
        return [items[index]]
    if module.display_mode == ImageModule.DisplayMode.ORDERED_COUNT:
        return items[:module.images_count]
    if module.display_mode == ImageModule.DisplayMode.RANDOM_COUNT:
        return random.sample(items, min(module.images_count, len(items)))
    return items
