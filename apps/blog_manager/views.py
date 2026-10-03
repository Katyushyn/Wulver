from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.generic import DetailView, ListView

from apps.core_manager.seo import build_seo_context
from apps.core_manager.models import SiteSettings
from .context_processors import get_latest_blog_articles
from .models import Article as ArticleModel, BlogSettings, Category


def get_category_template(category, page_number=None):
    settings = BlogSettings.get_solo()
    is_paginated = page_number and str(page_number) != "1"

    if is_paginated:
        return (
            category.paginated_theme_template
            or settings.default_paginated_category_template
            or category.theme_template
            or settings.default_category_template
        )

    return category.theme_template or settings.default_category_template


def get_article_template(article):
    settings = BlogSettings.get_solo()

    return (
        article.theme_template
        or getattr(article.category, "article_theme_template", None)
        or settings.default_article_template
    )


def _published_articles():
    return (
        ArticleModel.objects.select_related("category")
        .prefetch_related("tags")
        .filter(
            is_published=True,
            publish__lte=timezone.now(),
            category__isnull=False,
        )
        .order_by("-publish", "-id")
    )


def _category_with_children_ids(category):
    ids = [category.pk]
    pending = [category.pk]

    while pending:
        child_ids = list(
            Category.objects.filter(parent_id__in=pending).values_list("id", flat=True)
        )
        ids.extend(child_ids)
        pending = child_ids

    return ids


def _article_navigation(article):
    category_ids = _category_with_children_ids(article.category)
    articles = _published_articles().filter(category_id__in=category_ids)

    return {
        "prev_article": articles.filter(publish__lt=article.publish).first(),
        "next_article": (
            articles.filter(publish__gt=article.publish)
            .order_by("publish", "id")
            .first()
        ),
    }


def _sidebar_context():
    site_settings = SiteSettings.get_solo()

    return {
        "categories": Category.objects.order_by(
            "parent_id",
            "sort_order",
            "title",
        ),
        "latest_blog_articles": get_latest_blog_articles(
            site_settings.latest_articles_count
        ),
    }


def get_article_context(request, article):
    context = _sidebar_context()
    context.update(
        build_seo_context(
            request,
            page=article,
        )
    )
    context.update(
        {
            "article": article,
            "tegs_article": article.tags.order_by("title"),
            "category": article.category,
            "title": article.title,
        }
    )
    context.update(_article_navigation(article))
    return context


class BlogCategoryView(ListView):
    allow_empty = True
    context_object_name = "articles"
    model = ArticleModel

    def get_paginate_by(self, queryset):
        return self.category_obj.articles_per_page

    def dispatch(self, request, *args, **kwargs):
        self.category_obj = get_object_or_404(
            Category.objects.select_related(
                "theme_template",
                "theme_template__theme",
                "paginated_theme_template",
                "paginated_theme_template__theme",
            ),
            slug=kwargs["category_slug"],
        )

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        category_ids = _category_with_children_ids(self.category_obj)

        return _published_articles().filter(category_id__in=category_ids)

    def get_template_names(self):
        page_number = self.request.GET.get(self.page_kwarg)
        template = get_category_template(self.category_obj, page_number)

        if not template:
            raise Http404("Category template is not configured.")

        return [
            f"{template.theme.slug}/{template.slug}.html"
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(_sidebar_context())
        context.update(
            build_seo_context(
                self.request,
                page=self.category_obj,
            )
        )
        context.update(
            {
                "category": self.category_obj,
                "intro": self.category_obj.intro,
            }
        )

        return context


def category(request, category_slug):
    return BlogCategoryView.as_view()(request, category_slug=category_slug)


class Article(DetailView):
    context_object_name = "article"
    model = ArticleModel
    slug_url_kwarg = "post_slug"

    def get_queryset(self):
        return (
            _published_articles()
            .select_related(
                "category",
                "category__article_theme_template",
                "category__article_theme_template__theme",
                "theme_template",
                "theme_template__theme",
            )
            .filter(category__slug=self.kwargs["category_slug"])
        )

    def get_template_names(self):
        template = get_article_template(self.object)

        if not template:
            raise Http404("Article template is not configured.")

        return [
            f"{template.theme.slug}/{template.slug}.html"
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_article_context(self.request, self.object))
        return context
