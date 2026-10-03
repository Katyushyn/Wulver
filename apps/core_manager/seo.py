import json
import mimetypes
from copy import deepcopy
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.conf import settings
from django.urls import translate_url
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import get_language, override

from .models import SiteSettings


def _split_csv(value):
    return [
        item.strip()
        for item in (value or "").split(",")
        if item.strip()
    ]


def _split_lines(value):
    return [
        item.strip()
        for item in (value or "").splitlines()
        if item.strip()
    ]


def _absolute_file_url(request, file_field):
    if not file_field:
        return ""

    return request.build_absolute_uri(file_field.url)


def get_site_url(request, site_settings):
    if site_settings.site_url:
        return site_settings.site_url.rstrip("/")

    return f"{request.scheme}://{request.get_host()}"


def get_request_language(request):
    return (
        getattr(request, "LANGUAGE_CODE", "")
        or get_language()
        or settings.LANGUAGE_CODE
    )


def get_og_locale(request):
    language = get_request_language(request)
    language_key = language.replace("-", "_").split("_", 1)[0].lower()
    default_locales = {
        "en": "en_US",
        "uk": "uk_UA",
    }
    locale = settings.OG_LOCALE_BY_LANGUAGE.get(language_key)
    if locale and "_" in locale:
        return locale

    return default_locales.get(language_key, locale or language.replace("-", "_"))


def get_canonical_url(request, allowed_params):
    url_parts = list(urlparse(request.build_absolute_uri()))
    query = parse_qs(url_parts[4], keep_blank_values=True)
    allowed = set(_split_csv(allowed_params)) & {"page"}
    filtered_query = {}

    # Pagination is the only query parameter that may identify a distinct
    # canonical document. Page one is the clean collection URL, while later
    # pages keep a single normalized positive page number.
    page_values = query.get("page", [])
    if "page" in allowed and set(query) == {"page"} and len(page_values) == 1:
        try:
            page_number = int(page_values[0])
        except (TypeError, ValueError):
            page_number = 0
        if page_number > 1:
            filtered_query["page"] = str(page_number)

    url_parts[4] = urlencode(filtered_query, doseq=True)
    return urlunparse(url_parts).rstrip("?")


def get_alternate_urls(canonical_url, current_language):
    with override(current_language):
        return {
            lang_code: translate_url(canonical_url, lang_code)
            for lang_code, _language_name in settings.LANGUAGES
        }


def build_alternate_links(alternate_urls, x_default_url):
    links = format_html_join(
        "\n",
        '<link rel="alternate" hreflang="{}" href="{}">',
        alternate_urls.items(),
    )
    if x_default_url:
        links = format_html(
            '{}\n<link rel="alternate" hreflang="x-default" href="{}">',
            links,
            x_default_url,
        )
    return links


def build_article_meta(seo_object):
    if getattr(getattr(seo_object, "_meta", None), "label_lower", "") != "blog_manager.article":
        return ""

    lines = [
        format_html(
            '<meta property="article:published_time" content="{}">',
            seo_object.publish.isoformat(),
        ),
        format_html(
            '<meta property="article:modified_time" content="{}">',
            seo_object.updated.isoformat(),
        ),
    ]
    if seo_object.author:
        author_name = seo_object.author.get_full_name() or str(seo_object.author)
        lines.append(format_html('<meta property="article:author" content="{}">', author_name))
    if seo_object.category:
        lines.append(format_html('<meta property="article:section" content="{}">', seo_object.category.title))
    lines.extend(
        format_html('<meta property="article:tag" content="{}">', tag.title)
        for tag in seo_object.tags.all()
    )
    return format_html_join("\n", "{}", ((line,) for line in lines))


def get_preview_metadata(preview_image):
    if not preview_image:
        return "", "", ""

    mime = mimetypes.guess_type(preview_image.name)[0] or "image/jpeg"
    try:
        width = preview_image.width
        height = preview_image.height
    except (FileNotFoundError, OSError, ValueError):
        width = ""
        height = ""
    return mime, width, height


def _merge_schema_dicts(base, overrides):
    result = deepcopy(base) if isinstance(base, dict) else {}

    for key, value in (overrides or {}).items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _merge_schema_dicts(result[key], value)
        else:
            result[key] = deepcopy(value)

    return result


def _build_article_schema(
    request,
    site_settings,
    article,
    base_schema,
    title,
    description,
):
    if not isinstance(base_schema, dict):
        base_schema = {}

    site_url = get_site_url(request, site_settings)
    site_home_url = f"{site_url}/"
    allowed_params = (
        getattr(article, "canonical_allowed_params", "")
        or site_settings.canonical_allowed_params
    )
    page_url = get_canonical_url(request, allowed_params)
    language = get_request_language(request).replace("_", "-").lower()
    preview_image = (
        getattr(article, "preview_image", None)
        or getattr(article, "img_crop", None)
        or getattr(article, "img", None)
        or site_settings.default_preview_image
    )

    author_name = site_settings.person_name or site_settings.author_name
    if not author_name and getattr(article, "author", None):
        author_name = article.author.get_full_name() or str(article.author)

    author = {
        "@type": "Person",
        "@id": f"{site_home_url}#person",
        "url": site_home_url,
    }
    if author_name:
        author["name"] = author_name
    author_image = _absolute_file_url(request, site_settings.person_image)
    if author_image:
        author["image"] = author_image
    same_as = _split_lines(site_settings.same_as_links)
    if same_as:
        author["sameAs"] = same_as

    publisher = {
        "@type": "Organization",
        "@id": f"{site_home_url}#organization",
        "url": site_home_url,
    }
    if site_settings.organization_name:
        publisher["name"] = site_settings.organization_name
    publisher_logo = _absolute_file_url(
        request,
        site_settings.organization_logo,
    )
    if publisher_logo:
        publisher["logo"] = {
            "@type": "ImageObject",
            "url": publisher_logo,
        }

    dynamic_schema = {
        "@context": "https://schema.org",
        "@type": base_schema.get("@type") or "TechArticle",
        "@id": f"{page_url}#article",
        "url": page_url,
        "headline": title,
        "description": description,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": page_url,
        },
        "isPartOf": {"@id": f"{site_home_url}#website"},
        "inLanguage": language,
        "isAccessibleForFree": True,
        "author": author,
        "publisher": publisher,
    }

    if preview_image:
        image_url = _absolute_file_url(request, preview_image)
        dynamic_schema["image"] = [image_url]
        dynamic_schema["thumbnailUrl"] = image_url

    if getattr(article, "publish", None):
        dynamic_schema["datePublished"] = article.publish.isoformat()
    if getattr(article, "updated", None):
        dynamic_schema["dateModified"] = article.updated.isoformat()

    category = getattr(article, "category", None)
    if category:
        dynamic_schema["articleSection"] = category.title

    tags = list(article.tags.all()) if getattr(article, "pk", None) else []
    tag_titles = [tag.title for tag in tags if tag.title]
    keyword_values = _split_csv(getattr(article, "keywords", ""))
    keywords = list(dict.fromkeys(keyword_values + tag_titles))
    if keywords:
        dynamic_schema["keywords"] = keywords
    if tag_titles:
        dynamic_schema["about"] = [
            {"@type": "Thing", "name": tag_title}
            for tag_title in tag_titles
        ]

    schema = _merge_schema_dicts(base_schema, dynamic_schema)
    custom_schema = getattr(article, "schema_graph", None)
    if isinstance(custom_schema, dict):
        schema = _merge_schema_dicts(schema, custom_schema)

    return schema


def build_schema_graph(request, site_settings, seo_object=None, title="", description=""):
    site_url = get_site_url(request, site_settings)
    page_url = request.build_absolute_uri()

    model_label = getattr(
        getattr(seo_object, "_meta", None),
        "label_lower",
        "",
    )

    if model_label == "blog_manager.article":
        from apps.blog_manager.models import BlogSettings

        default_schema = BlogSettings.get_solo().default_article_schema_graph
        custom_schema = getattr(seo_object, "schema_graph", None)
        if custom_schema and not isinstance(custom_schema, dict):
            return custom_schema

        return _build_article_schema(
            request,
            site_settings,
            seo_object,
            default_schema,
            title or getattr(seo_object, "title", ""),
            description or getattr(seo_object, "description", ""),
        )

    if seo_object and getattr(seo_object, "schema_graph", None):
        return seo_object.schema_graph

    if seo_object:
        model_meta = getattr(seo_object, "_meta", None)
        blog_schema_field = {
            "blog_manager.category": "default_category_schema_graph",
            "blog_manager.article": "default_article_schema_graph",
        }.get(getattr(model_meta, "label_lower", ""))

        if blog_schema_field:
            from apps.blog_manager.models import BlogSettings

            blog_schema_graph = getattr(
                BlogSettings.get_solo(),
                blog_schema_field,
                None,
            )
            if blog_schema_graph:
                return blog_schema_graph

    if site_settings.default_schema_graph:
        return site_settings.default_schema_graph

    graph = [
        {
            "@type": "WebSite",
            "@id": f"{site_url}#website",
            "url": site_url,
            "name": site_settings.site_name,
        },
    ]

    if site_settings.organization_name:
        organization = {
            "@type": "Organization",
            "@id": f"{site_url}#organization",
            "name": site_settings.organization_name,
            "url": site_url,
        }

        logo_url = _absolute_file_url(request, site_settings.organization_logo)
        if logo_url:
            organization["logo"] = {
                "@type": "ImageObject",
                "url": logo_url,
            }

        graph.append(organization)

    if site_settings.person_name:
        person = {
            "@type": "Person",
            "@id": f"{site_url}#person",
            "name": site_settings.person_name,
            "url": site_url,
        }

        image_url = _absolute_file_url(request, site_settings.person_image)
        if image_url:
            person["image"] = image_url

        if site_settings.person_job_title:
            person["jobTitle"] = site_settings.person_job_title

        same_as = _split_lines(site_settings.same_as_links)
        if same_as:
            person["sameAs"] = same_as

        graph.append(person)

    graph.append(
        {
            "@type": "WebPage",
            "@id": f"{page_url}#webpage",
            "url": page_url,
            "name": title or site_settings.site_name,
            "description": description,
            "isPartOf": {"@id": f"{site_url}#website"},
        }
    )

    return {
        "@context": "https://schema.org",
        "@graph": graph,
    }


def _first_nonempty(*values):
    for value in values:
        if isinstance(value, str):
            value = value.strip()

        if value:
            return value

    return ""


def _get_noindex(seo_object):
    if getattr(seo_object, "noindex", False):
        return True

    category = getattr(seo_object, "category", None)
    if getattr(category, "noindex", False):
        return True

    return False


def build_seo_context(request, page=None, menu_item=None):
    site_settings = SiteSettings.get_solo()
    seo_object = page

    title = _first_nonempty(
        getattr(seo_object, "title", ""),
        site_settings.title,
        site_settings.site_name,
    )
    description = _first_nonempty(
        getattr(seo_object, "description", ""),
        site_settings.description,
    )
    keywords = getattr(seo_object, "keywords", "")
    preview_image = (
        getattr(seo_object, "preview_image", None)
        or getattr(seo_object, "img_crop", None)
        or getattr(seo_object, "img", None)
        or site_settings.default_preview_image
    )
    allowed_params = (
        getattr(seo_object, "canonical_allowed_params", "")
        or site_settings.canonical_allowed_params
    )
    schema_graph = build_schema_graph(
        request,
        site_settings,
        seo_object=seo_object,
        title=title,
        description=description,
    )
    canonical_url = get_canonical_url(request, allowed_params)
    alternate_urls = get_alternate_urls(
        canonical_url,
        get_request_language(request),
    )
    default_language = settings.LANGUAGE_CODE
    x_default_url = alternate_urls.get(
        default_language,
        translate_url(canonical_url, default_language),
    )
    preview_mime, preview_width, preview_height = get_preview_metadata(preview_image)
    image_alt = site_settings.default_image_alt or title
    noindex = _get_noindex(seo_object)
    current_language = get_request_language(request).replace("_", "-").lower()
    language_urls = [
        {
            "code": lang_code,
            "name": language_name,
            "url": alternate_urls[lang_code],
            "is_active": lang_code.replace("_", "-").lower() == current_language,
        }
        for lang_code, language_name in settings.LANGUAGES
    ]

    return {
        "request": request,
        "site_settings": site_settings,
        "lang": get_request_language(request),
        "title": title,
        "keywords": keywords,
        "description": description,
        "preview": preview_image.url if preview_image else "",
        "preview_url": _absolute_file_url(request, preview_image),
        "base_url": get_site_url(request, site_settings),
        "twitter": site_settings.twitter_handle,
        "author": site_settings.author_name,
        "og_site_name": site_settings.og_site_name or site_settings.site_name,
        "og_locale": get_og_locale(request),
        "type_content": getattr(seo_object, "og_type", "") or site_settings.default_og_type,
        "canonical_url": canonical_url,
        "alternate_urls": alternate_urls,
        "language_urls": language_urls,
        "x_default_url": x_default_url,
        "alternate_links": build_alternate_links(alternate_urls, x_default_url),
        "robots": "noindex, follow" if noindex else "index, follow",
        "preview_mime": preview_mime,
        "preview_width": preview_width,
        "preview_height": preview_height,
        "image_alt": image_alt,
        "article_meta": build_article_meta(seo_object),
        "theme_color": site_settings.theme_color,
        "schema_graph_data": schema_graph,
        # JSON-LD lives inside a script element.  JSON escaping alone does not
        # escape HTML's closing </script> sequence, so encode HTML-significant
        # characters before marking the serialized JSON as safe.
        "schema_graph": mark_safe(
            json.dumps(schema_graph, ensure_ascii=False)
            .replace("<", "\\u003C")
            .replace(">", "\\u003E")
            .replace("&", "\\u0026")
        ),
        "google_analytics_id": site_settings.google_analytics_id,
        "google_tag_manager_id": site_settings.google_tag_manager_id,
        "maintenance_mode": site_settings.maintenance_mode,
        "maintenance_message": site_settings.maintenance_message,
        "noindex": noindex,
    }


class SEOContextMixin:
    seo_page = None

    def get_seo_page(self):
        return self.seo_page

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            build_seo_context(
                self.request,
                page=self.get_seo_page(),
            )
        )
        return context
