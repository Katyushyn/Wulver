from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _

from apps.blog_manager.models import Article, Category

from .models import Page, SiteSettings


def get_cms_link_options(content_type, query="", page=1, language=None):
    """Return CMS objects in the common format used by admin code editors."""
    available_languages = {code for code, _name in settings.LANGUAGES}
    language = language if language in available_languages else settings.LANGUAGE_CODE
    page = max(1, page)
    page_size = 30
    offset = (page - 1) * page_size
    query = query.strip()

    with translation.override(language):
        home_page = SiteSettings.get_solo().home_page
        home_url_tag = "{% url 'core_manager:home' %}"

        if content_type == "home":
            return {
                "items": [{
                    "id": home_page.pk if home_page else None,
                    "title": _("Home"),
                    "slug": "",
                    "url": reverse("core_manager:home"),
                    "url_tag": home_url_tag,
                    "reference": "home",
                }],
                "page": 1,
                "has_more": False,
            }

        if content_type == "page":
            queryset = Page.objects.filter(is_published=True)
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) | Q(slug__icontains=query)
                )
            objects = list(queryset.order_by("title", "id")[offset:offset + page_size + 1])
            items = [
                {
                    "id": obj.pk,
                    "title": obj.title,
                    "slug": obj.slug,
                    "url": (
                        reverse("core_manager:home")
                        if home_page and home_page.pk == obj.pk
                        else reverse("core_manager:slug_detail", kwargs={"slug": obj.slug})
                    ),
                    "url_tag": (
                        home_url_tag
                        if home_page and home_page.pk == obj.pk
                        else "{% url 'core_manager:slug_detail' slug='" + obj.slug + "' %}"
                    ),
                    "reference": f"page:{obj.pk}",
                }
                for obj in objects[:page_size]
            ]
        elif content_type == "category":
            queryset = Category.objects.all()
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) | Q(slug__icontains=query)
                )
            objects = list(queryset.order_by("title", "id")[offset:offset + page_size + 1])
            items = [
                {
                    "id": obj.pk,
                    "title": obj.title,
                    "slug": obj.slug,
                    "url": obj.get_absolute_url(),
                    "url_tag": "{% url 'blog:category' category_slug='" + obj.slug + "' %}",
                    "reference": f"category:{obj.pk}",
                }
                for obj in objects[:page_size]
            ]
        elif content_type == "article":
            queryset = Article.objects.select_related("category").filter(
                is_published=True,
                category__isnull=False,
            )
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query)
                    | Q(slug__icontains=query)
                    | Q(category__title__icontains=query)
                )
            objects = list(queryset.order_by("-publish", "-id")[offset:offset + page_size + 1])
            items = [
                {
                    "id": obj.pk,
                    "title": obj.title,
                    "slug": obj.slug,
                    "category": obj.category.title,
                    "url": obj.get_absolute_url(),
                    "url_tag": "{% url 'blog:post' category_slug='"
                        + obj.category.slug
                        + "' post_slug='"
                        + obj.slug
                        + "' %}",
                    "reference": f"article:{obj.pk}",
                }
                for obj in objects[:page_size]
            ]
        else:
            raise ValueError("Unknown content type")

    return {
        "items": items,
        "page": page,
        "has_more": len(objects) > page_size,
    }
