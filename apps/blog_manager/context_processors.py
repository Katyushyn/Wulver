from django.db.models import Count

from .models import Tag


TAG_CLOUD_LIMIT = 21


def get_tag_cloud():
    tags = list(
        Tag.objects.annotate(article_count=Count("article"))
        .filter(article_count__gt=0)
        .order_by("-article_count", "title")[:TAG_CLOUD_LIMIT]
    )

    return tags


def blog_context(request):
    return {
        "tags_cloud": get_tag_cloud(),
    }
