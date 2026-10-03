from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import translation

from .models import Page, SiteSettings
from .redirects import register_localized_redirects


def _localized_urls(view_name, kwargs=None):
    urls = {}
    for language, _name in settings.LANGUAGES:
        with translation.override(language):
            urls[language] = reverse(view_name, kwargs=kwargs)
    return urls


def _page_urls(page_id, slug):
    is_home = SiteSettings.objects.filter(pk=1, home_page_id=page_id).exists()
    if is_home:
        return _localized_urls("core_manager:home")
    return _localized_urls("core_manager:slug_detail", {"slug": slug})


def _category_urls(slug):
    return _localized_urls("blog:category", {"category_slug": slug})


def _article_urls(category_slug, article_slug):
    return _localized_urls(
        "blog:post",
        {"category_slug": category_slug, "post_slug": article_slug},
    )


@receiver(pre_save, sender=Page)
def remember_page_url(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return
    old = sender.objects.filter(pk=instance.pk).only("slug").first()
    if old and old.slug != instance.slug:
        instance._redirect_old_urls = _page_urls(instance.pk, old.slug)


@receiver(post_save, sender=Page)
def create_page_redirect(sender, instance, created=False, raw=False, **kwargs):
    old_urls = getattr(instance, "_redirect_old_urls", None)
    if raw or created or not old_urls:
        return
    register_localized_redirects(
        old_urls,
        _page_urls(instance.pk, instance.slug),
        note="Page URL changed automatically.",
    )


@receiver(pre_save, sender="blog_manager.Article")
def remember_article_url(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return
    old = sender.objects.select_related("category").filter(pk=instance.pk).first()
    if (
        old
        and old.category_id
        and (old.slug != instance.slug or old.category_id != instance.category_id)
    ):
        instance._redirect_old_urls = _article_urls(old.category.slug, old.slug)


@receiver(post_save, sender="blog_manager.Article")
def create_article_redirect(sender, instance, created=False, raw=False, **kwargs):
    old_urls = getattr(instance, "_redirect_old_urls", None)
    if raw or created or not old_urls or not instance.category_id:
        return
    register_localized_redirects(
        old_urls,
        _article_urls(instance.category.slug, instance.slug),
        note="Article URL changed automatically.",
    )


@receiver(pre_save, sender="blog_manager.Category")
def remember_category_urls(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return
    old = sender.objects.filter(pk=instance.pk).only("slug").first()
    if not old or old.slug == instance.slug:
        return
    instance._redirect_old_urls = _category_urls(old.slug)
    instance._redirect_article_slugs = list(
        instance.article_set.values_list("slug", flat=True)
    )
    instance._redirect_old_category_slug = old.slug


@receiver(post_save, sender="blog_manager.Category")
def create_category_redirects(sender, instance, created=False, raw=False, **kwargs):
    old_urls = getattr(instance, "_redirect_old_urls", None)
    if raw or created or not old_urls:
        return
    register_localized_redirects(
        old_urls,
        _category_urls(instance.slug),
        note="Category URL changed automatically.",
    )
    old_category_slug = getattr(instance, "_redirect_old_category_slug", "")
    for article_slug in getattr(instance, "_redirect_article_slugs", []):
        register_localized_redirects(
            _article_urls(old_category_slug, article_slug),
            _article_urls(instance.slug, article_slug),
            note="Article URL changed because its category URL changed.",
        )
