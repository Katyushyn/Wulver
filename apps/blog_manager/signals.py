from django.core.files.storage import default_storage
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import ArticleImage


@receiver(post_delete, sender=ArticleImage)
def delete_article_image_file(sender, instance, **_kwargs):
    del sender
    if instance.image:
        default_storage.delete(instance.image.name)
