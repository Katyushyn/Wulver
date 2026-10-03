from django.db.models import Count
from django.utils import timezone

from apps.core_manager.models import SiteSettings

from .models import Article, Tag


TAG_CLOUD_LIMIT = 21


def get_latest_blog_articles(limit):
    limit = max(int(limit or 0), 0)

    if limit == 0:
        return Article.objects.none()

    return (
        Article.objects.select_related("category")
        .filter(
            is_published=True,
            publish__lte=timezone.now(),
            category__isnull=False,
        )
        .order_by("-publish", "-id")[:limit]
    )


def get_tag_cloud():
    tags = list(
        Tag.objects.annotate(article_count=Count("article"))
        .filter(article_count__gt=0)
        .order_by("-article_count", "title")[:TAG_CLOUD_LIMIT]
    )

    return tags


def blog_context(request):
    site_settings = SiteSettings.get_solo()

    return {
        "latest_blog_articles": get_latest_blog_articles(
            site_settings.latest_articles_count
        ),
        "tags_cloud": get_tag_cloud(),
    }
