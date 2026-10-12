from html import unescape

from django import template
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import CharField, F, Window
from django.db.models.functions import Cast, RowNumber
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django_comments import get_model

from apps.blog_manager.models import Article
from apps.blog_manager.templatetags.blog_modules import _category_ids_with_descendants
from apps.comments_manager.models import LatestCommentsModule

register = template.Library()


@register.simple_tag
def latest_comments_module(slug):
    module = LatestCommentsModule.objects.filter(slug=slug, is_active=True).first()
    if module is None:
        return []
    category_ids = set(module.categories.values_list("pk", flat=True))
    if not category_ids:
        return []
    if module.include_descendants:
        category_ids = _category_ids_with_descendants(category_ids)
    articles = Article.objects.filter(
        category_id__in=category_ids, is_published=True, publish__lte=timezone.now(),
    )
    comments = list(
        get_model().objects.filter(
            content_type=ContentType.objects.get_for_model(Article),
            object_pk__in=articles.annotate(string_pk=Cast("pk", CharField())).values("string_pk"),
            site_id=settings.SITE_ID, is_public=True, is_removed=False,
            submit_date__lte=timezone.now(),
        ).annotate(
            article_rank=Window(
                expression=RowNumber(), partition_by=[F("object_pk")],
                order_by=[F("submit_date").desc(), F("pk").desc()],
            ),
        ).filter(article_rank__lte=module.per_article_limit)
        .order_by("-submit_date", "-pk")[:module.comments_count]
    )
    article_map = articles.in_bulk([int(comment.object_pk) for comment in comments])
    return [
        {
            "article": article_map[int(comment.object_pk)],
            "excerpt": Truncator(unescape(strip_tags(comment.comment))).words(module.excerpt_words),
        }
        for comment in comments
    ]
