import random
import math

from django import template
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags

from apps.blog_manager.models import Article, Category, LatestArticlesModule, Tag, TagModule


register = template.Library()


@register.simple_tag
def blog_authors():
    """Active public article authors, excluding administrator accounts."""
    author_ids = Article.objects.filter(
        is_published=True, publish__lte=timezone.now(),
    ).values("author_id")
    return (
        get_user_model().objects.filter(is_active=True, is_superuser=False, pk__in=author_ids)
        .select_related("userprofile")
        .order_by("first_name", "last_name", "pk")
    )


@register.filter
def reading_time(article):
    text = " ".join((getattr(article, "intro", ""), getattr(article, "body", "")))
    words = len(strip_tags(text).split())
    return max(1, math.ceil(words / 200))


@register.simple_tag
def module_author(module_slug):
    module = LatestArticlesModule.objects.filter(slug=module_slug, is_active=True).first()
    if module is None:
        return None
    return module.authors.filter(is_active=True).annotate(
        published_count=Count("article", filter=Q(article__is_published=True, article__publish__lte=timezone.now()))
    ).first()


def _category_ids_with_descendants(category_ids):
    category_ids = set(category_ids)
    pending = set(category_ids)

    while pending:
        child_ids = set(
            Category.objects.filter(parent_id__in=pending).values_list("pk", flat=True)
        )
        child_ids -= category_ids
        category_ids.update(child_ids)
        pending = child_ids

    return category_ids


@register.simple_tag
def latest_articles_module(module_slug):
    module = (
        LatestArticlesModule.objects
        .prefetch_related("categories", "tags", "authors")
        .filter(slug=module_slug, is_active=True)
        .first()
    )
    if module is None:
        return Article.objects.none()

    category_ids = set(module.categories.values_list("pk", flat=True))
    if not category_ids:
        return Article.objects.none()

    if module.include_descendants:
        category_ids = _category_ids_with_descendants(category_ids)

    ordering = {
        LatestArticlesModule.Ordering.NEWEST: ("-publish", "-pk"),
        LatestArticlesModule.Ordering.OLDEST: ("publish", "pk"),
        LatestArticlesModule.Ordering.TITLE: ("title", "pk"),
    }[module.ordering]

    articles = (
        Article.objects
        .select_related("category")
        .prefetch_related("tags")
        .filter(
            category_id__in=category_ids,
            is_published=True,
            publish__lte=timezone.now(),
        )
    )
    tag_ids = module.tags.values_list("pk", flat=True)
    author_ids = module.authors.values_list("pk", flat=True)
    if author_ids:
        articles = articles.filter(author_id__in=author_ids)
    if tag_ids:
        articles = articles.filter(tags__in=tag_ids).distinct()

    return articles.order_by(*ordering)[:module.articles_count]


def _tag_module_queryset(context, module):
    if module.source == TagModule.Source.CURRENT_ARTICLE:
        article = context.get("article")
        if not isinstance(article, Article):
            article = context.get("object")
        if not isinstance(article, Article):
            return Tag.objects.none()
        queryset = article.tags.all()
    elif module.source == TagModule.Source.CURRENT_CATEGORY:
        category = context.get("category")
        if not isinstance(category, Category):
            article = context.get("article")
            category = getattr(article, "category", None)
        if not isinstance(category, Category):
            return Tag.objects.none()
        queryset = category.tags.all()
    else:
        queryset = Tag.objects.all()

    queryset = queryset.annotate(article_count=Count("article", distinct=True))
    if module.source == TagModule.Source.GLOBAL_CLOUD:
        queryset = queryset.filter(article_count__gt=0)

    ordering = {
        TagModule.Ordering.TITLE: ("title", "pk"),
        TagModule.Ordering.POPULARITY: ("-article_count", "title", "pk"),
    }[module.ordering]
    return queryset.order_by(*ordering)[:module.tags_count]


@register.simple_tag(takes_context=True)
def tags_module(context, module_slug):
    module = TagModule.objects.filter(slug=module_slug, is_active=True).first()
    if module is None:
        return []

    css_classes = module.parsed_classes()
    all_classes = " ".join(css_classes)
    items = []

    for index, tag in enumerate(_tag_module_queryset(context, module)):
        css_class = ""
        if css_classes:
            if module.class_mode == TagModule.ClassMode.ALL:
                css_class = all_classes
            elif module.class_mode == TagModule.ClassMode.RANDOM:
                css_class = random.choice(css_classes)
            else:
                css_class = css_classes[index % len(css_classes)]

        items.append({
            "tag": tag,
            "title": tag.title,
            "slug": tag.slug,
            "article_count": tag.article_count,
            "css_class": css_class,
        })

    return items
