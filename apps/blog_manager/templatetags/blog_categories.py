from django import template
from django.db.models import Count, Q
from django.utils import timezone

from apps.blog_manager.models import Category

register = template.Library()


@register.simple_tag
def get_blog_category_children(parent_id, with_counts=False):
    categories = Category.objects.filter(parent_id=parent_id)
    if with_counts:
        categories = categories.annotate(
            article_count=Count(
                "article",
                filter=Q(article__is_published=True, article__publish__lte=timezone.now()),
            )
        )
    return categories.order_by(
        "sort_order",
        "title",
        "id",
    )
