from types import SimpleNamespace
from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.http import Http404, HttpResponse
from django.template import loader
from django.urls import reverse
from django.utils import timezone
from django.utils.http import http_date

from apps.blog_manager.models import Article, Category
from apps.theme_manager.models import TemplateType

from .models import Page, SitemapSettings, SiteSettings


SITEMAP_CACHE_VERSION_KEY = "wulver:sitemap:version"
SITEMAP_CACHE_SCHEMA = "v3"
SITEMAP_URL_LIMIT = 50000


def invalidate_sitemap_cache(**kwargs):
    cache.set(SITEMAP_CACHE_VERSION_KEY, timezone.now().timestamp(), timeout=None)


def _language_field_value(item, field_name, language_code):
    suffix = language_code.lower().replace("-", "_")
    return getattr(item, f"{field_name}_{suffix}", "")


class LocalizedSitemap(Sitemap):
    i18n = True
    translation_fields = ("title",)

    def __init__(self, configuration):
        self.configuration = configuration
        self.alternates = configuration.include_alternates
        self.x_default = configuration.include_alternates

    def get_languages_for_item(self, item):
        default_language = settings.LANGUAGE_CODE
        if not self.configuration.include_translations:
            return [default_language]

        available = []
        for language_code, _language_name in settings.LANGUAGES:
            has_content = any(
                str(_language_field_value(item, field, language_code) or "").strip()
                for field in self.translation_fields
            )
            if has_content or language_code == default_language:
                available.append(language_code)
        return available or [default_language]


class HomepageSitemap(LocalizedSitemap):
    translation_fields = ("title", "description")

    def items(self):
        if not self.configuration.include_homepage:
            return Page.objects.none()
        homepage_id = SiteSettings.get_solo().home_page_id
        if not homepage_id:
            return Page.objects.none()
        return Page.objects.filter(
            pk=homepage_id,
            is_published=True,
            noindex=False,
            template__template_type=TemplateType.CHILDREN_PAGE,
            template__is_active=True,
            template__theme__is_active=True,
        )

    def priority(self, item):
        return self.configuration.homepage_priority

    def lastmod(self, item):
        return item.updated_at


class PageSitemap(LocalizedSitemap):
    translation_fields = ("title", "description")

    def items(self):
        if not self.configuration.include_pages:
            return Page.objects.none()
        homepage_id = SiteSettings.get_solo().home_page_id
        return (
            Page.objects
            .filter(
                is_published=True,
                noindex=False,
                template__template_type=TemplateType.CHILDREN_PAGE,
                template__is_active=True,
                template__theme__is_active=True,
            )
            .exclude(pk=homepage_id)
            .order_by("pk")
        )

    def priority(self, item):
        return self.configuration.page_priority

    def lastmod(self, item):
        return item.updated_at


class CategorySitemap(LocalizedSitemap):
    translation_fields = ("title", "description", "intro")

    def items(self):
        if not self.configuration.include_categories:
            return Category.objects.none()
        return Category.objects.filter(noindex=False).order_by("pk")

    def priority(self, item):
        return self.configuration.category_priority

    def lastmod(self, item):
        return item.updated


class ArticleSitemap(LocalizedSitemap):
    translation_fields = ("title", "description", "body")

    def items(self):
        if not self.configuration.include_articles:
            return Article.objects.none()
        return (
            Article.objects
            .filter(
                is_published=True,
                publish__lte=timezone.now(),
                noindex=False,
                category__isnull=False,
                category__noindex=False,
            )
            .select_related("category")
            .order_by("pk")
        )

    def priority(self, item):
        return self.configuration.article_priority

    def lastmod(self, item):
        return item.updated


def configured_sitemaps(configuration=None):
    configuration = configuration or SitemapSettings.get_solo()
    maps = {}
    if configuration.include_homepage:
        maps["homepage"] = HomepageSitemap(configuration)
    if configuration.include_pages:
        maps["pages"] = PageSitemap(configuration)
    if configuration.include_categories:
        maps["categories"] = CategorySitemap(configuration)
    if configuration.include_articles:
        maps["articles"] = ArticleSitemap(configuration)
    return maps


def _public_origin(request):
    return request.scheme, request.get_host()


def _render_index(request, sitemaps):
    protocol, domain = _public_origin(request)
    entries = []
    all_sections_have_lastmod = True
    latest_lastmod = None

    for section, sitemap in sitemaps.items():
        section_lastmod = sitemap.get_latest_lastmod()
        if section_lastmod is None:
            all_sections_have_lastmod = False
        elif latest_lastmod is None or section_lastmod > latest_lastmod:
            latest_lastmod = section_lastmod

        section_path = reverse("sitemap-section", kwargs={"section": section})
        location = f"{protocol}://{domain}{section_path}"
        entries.append(SimpleNamespace(location=location, last_mod=section_lastmod))
        for page in range(2, sitemap.paginator.num_pages + 1):
            entries.append(
                SimpleNamespace(
                    location=f"{location}?p={page}",
                    last_mod=section_lastmod,
                )
            )

    headers = {"X-Robots-Tag": "noindex, noodp, noarchive"}
    if all_sections_have_lastmod and latest_lastmod:
        headers["Last-Modified"] = http_date(latest_lastmod.timestamp())
    content = loader.get_template("sitemap_index.xml").render(
        {"sitemaps": entries}
    )
    return HttpResponse(
        content,
        content_type="application/xml",
        headers=headers,
    )


def _render_section(request, sitemaps, section):
    if section not in sitemaps:
        raise Http404(f"No sitemap available for section: {section!r}")

    sitemap = sitemaps[section]
    protocol, domain = _public_origin(request)
    page = request.GET.get("p", 1)
    try:
        urls = sitemap.get_urls(
            page=page,
            site=SimpleNamespace(domain=domain),
            protocol=protocol,
        )
    except (EmptyPage, PageNotAnInteger) as error:
        raise Http404(f"Invalid sitemap page: {page!r}") from error

    headers = {"X-Robots-Tag": "noindex, noodp, noarchive"}
    latest_lastmod = getattr(sitemap, "latest_lastmod", None)
    if latest_lastmod:
        headers["Last-Modified"] = http_date(latest_lastmod.timestamp())
    content = loader.get_template("sitemap.xml").render({"urlset": urls})
    return HttpResponse(
        content,
        content_type="application/xml",
        headers=headers,
    )


def _render_combined(request, sitemaps):
    protocol, domain = _public_origin(request)
    site = SimpleNamespace(domain=domain)
    urls = []
    latest_lastmod = None
    all_entries_have_lastmod = True

    for sitemap in sitemaps.values():
        section_urls = sitemap.get_urls(page=1, site=site, protocol=protocol)
        urls.extend(section_urls)
        section_lastmod = getattr(sitemap, "latest_lastmod", None)
        if section_lastmod is None:
            all_entries_have_lastmod = False
        elif latest_lastmod is None or section_lastmod > latest_lastmod:
            latest_lastmod = section_lastmod

    headers = {"X-Robots-Tag": "noindex, noodp, noarchive"}
    if all_entries_have_lastmod and latest_lastmod:
        headers["Last-Modified"] = http_date(latest_lastmod.timestamp())
    content = loader.get_template("sitemap.xml").render({"urlset": urls})
    return HttpResponse(
        content,
        content_type="application/xml",
        headers=headers,
    )


def _cached_response(request, configuration, view, **view_kwargs):
    version = cache.get(SITEMAP_CACHE_VERSION_KEY, "initial")
    cache_key = (
        f"wulver:sitemap:{SITEMAP_CACHE_SCHEMA}:{version}:"
        f"{request.scheme}:{request.get_host()}:"
        f"{request.get_full_path()}"
    )
    cached = cache.get(cache_key) if configuration.cache_timeout else None
    if cached is not None:
        response = HttpResponse(
            cached["content"],
            status=cached["status"],
            content_type=cached["content_type"],
        )
        for name, value in cached["headers"].items():
            response[name] = value
        return response

    response = view(request, **view_kwargs)
    if hasattr(response, "render"):
        response.render()
    if configuration.cache_timeout and response.status_code == 200:
        excluded_headers = {"Content-Type", "Content-Length"}
        cache.set(
            cache_key,
            {
                "content": bytes(response.content),
                "status": response.status_code,
                "content_type": response.get("Content-Type", "application/xml"),
                "headers": {
                    name: value
                    for name, value in response.items()
                    if name not in excluded_headers
                },
            },
            timeout=configuration.cache_timeout,
        )
    return response


def sitemap_index(request):
    configuration = SitemapSettings.get_solo()
    if not configuration.enabled:
        raise Http404("Sitemap is disabled.")
    sitemaps = configured_sitemaps(configuration)
    total_urls = sum(sitemap.paginator.count for sitemap in sitemaps.values())
    view = _render_combined if total_urls <= SITEMAP_URL_LIMIT else _render_index
    return _cached_response(
        request,
        configuration,
        view,
        sitemaps=sitemaps,
    )


def sitemap_section(request, section):
    configuration = SitemapSettings.get_solo()
    if not configuration.enabled:
        raise Http404("Sitemap is disabled.")
    return _cached_response(
        request,
        configuration,
        _render_section,
        sitemaps=configured_sitemaps(configuration),
        section=section,
    )


def sitemap_stylesheet(request):
    content = loader.get_template("sitemap.xsl").render()
    return HttpResponse(content, content_type="text/xsl; charset=utf-8")
