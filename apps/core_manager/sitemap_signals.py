from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.blog_manager.models import Article, Category, Tag

from .models import Page, SitemapSettings, SiteSettings
from .sitemaps import invalidate_sitemap_cache


SITEMAP_MODELS = (Page, Category, Article, Tag, SitemapSettings, SiteSettings)


for sitemap_model in SITEMAP_MODELS:
    post_save.connect(
        invalidate_sitemap_cache,
        sender=sitemap_model,
        weak=False,
        dispatch_uid=f"wulver_sitemap_post_save_{sitemap_model._meta.label_lower}",
    )
    post_delete.connect(
        invalidate_sitemap_cache,
        sender=sitemap_model,
        weak=False,
        dispatch_uid=f"wulver_sitemap_post_delete_{sitemap_model._meta.label_lower}",
    )


@receiver(m2m_changed, sender=Article.tags.through)
def article_tags_changed(**kwargs):
    invalidate_sitemap_cache()
