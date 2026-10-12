import logging

from django import forms
from django.core import signing
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.template import TemplateDoesNotExist
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from apps.blog_manager.views import Article as BlogArticleView
from apps.blog_manager.views import BlogCategoryView
from apps.blog_manager.models import Article, Category
from .models import (
    ContactMessage,
    NewsletterSubscription,
    Page,
    SitemapSettings,
    SiteSettings,
)
from .seo import build_seo_context
from .security import client_ip, is_rate_limited, private_cache_key


logger = logging.getLogger(__name__)


def _settings_file_response(file_field, content_type):
    if not file_field:
        raise Http404("File is not configured.")

    try:
        return FileResponse(file_field.open("rb"), content_type=content_type)
    except FileNotFoundError as exc:
        raise Http404("File does not exist.") from exc


@require_GET
def favicon_ico(request):
    site_settings = SiteSettings.get_solo()
    return _settings_file_response(site_settings.favicon_ico, "image/x-icon")


@require_GET
def favicon_png(request):
    site_settings = SiteSettings.get_solo()
    return _settings_file_response(site_settings.favicon_png, "image/png")


@require_GET
def apple_touch_icon(request):
    site_settings = SiteSettings.get_solo()
    return _settings_file_response(site_settings.apple_touch_icon, "image/png")


@require_GET
def robots_txt(request):
    site_settings = SiteSettings.get_solo()
    sitemap_settings = SitemapSettings.get_solo()
    lines = [
        line
        for line in site_settings.robots_txt.splitlines()
        if not line.strip().lower().startswith("sitemap:")
    ]
    if sitemap_settings.enabled:
        sitemap_url = request.build_absolute_uri("/sitemap.xml")
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"Sitemap: {sitemap_url}")
    content = "\n".join(lines).strip()
    if content:
        content += "\n"
    return HttpResponse(content, content_type="text/plain")


def page_not_found(request, exception):
    from apps.theme_manager.models import TemplateType, ThemeTemplate

    site_settings = SiteSettings.get_solo()
    template = site_settings.error_404_template

    if template is None:
        template = (
            ThemeTemplate.objects
            .filter(
                template_type=TemplateType.ERROR_TEMPLATE,
                is_active=True,
                theme__is_active=True,
            )
            .select_related("theme")
            .order_by("pk")
            .first()
        )

    if (
        template
        and template.is_active
        and template.theme.is_active
        and template.template_type == TemplateType.ERROR_TEMPLATE
    ):
        error_title = _("Page not found")
        error_message = _("The requested page could not be found.")
        context = build_seo_context(request)
        context.update(
            {
                "error_code": 404,
                "error_title": error_title,
                "error_message": error_message,
                "title": error_title,
                "description": error_message,
                "keywords": "",
                "robots": "noindex, nofollow",
                "noindex": True,
                "canonical_url": "",
                "alternate_urls": {},
                "alternate_links": "",
                "x_default_url": "",
                "og_site_name": "",
                "preview": "",
                "preview_url": "",
                "article_meta": "",
                "schema_graph": "",
                "schema_graph_data": {},
                "is_error_page": True,
            }
        )

        try:
            response = render(
                request,
                f"{template.theme.slug}/{template.slug}.html",
                context,
                status=404,
            )
            response["X-Robots-Tag"] = "noindex, nofollow"
            return response
        except TemplateDoesNotExist:
            pass

    response = HttpResponseNotFound(
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"robots\" content=\"noindex, nofollow\">"
        "<title>" + _("Page not found") + "</title></head>"
        "<body><h1>404</h1><p>" + _("Page not found") + "</p></body></html>"
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _active_theme_template(configured_template, template_type):
    from apps.theme_manager.models import ThemeTemplate

    if (
        configured_template
        and configured_template.template_type == template_type
        and configured_template.is_active
        and configured_template.theme.is_active
    ):
        return configured_template

    return (
        ThemeTemplate.objects
        .filter(
            template_type=template_type,
            is_active=True,
            theme__is_active=True,
        )
        .select_related("theme")
        .order_by("pk")
        .first()
    )


def _query_values(query, *names, limit=20):
    values = []
    seen = set()

    for name in names:
        for raw_value in query.getlist(name):
            for value in raw_value.split(","):
                value = value.strip()
                normalized = value.casefold()
                if value and normalized not in seen:
                    values.append(value)
                    seen.add(normalized)
                if len(values) >= limit:
                    return values

    return values


def _category_search_ids(category_values):
    if not category_values:
        return []

    category_query = Q()
    for value in category_values:
        category_query |= Q(slug__iexact=value) | Q(title__iexact=value)

    category_ids = list(
        Category.objects.filter(category_query).values_list("pk", flat=True)
    )
    all_ids = set(category_ids)
    pending_ids = category_ids

    while pending_ids:
        pending_ids = list(
            Category.objects
            .filter(parent_id__in=pending_ids)
            .exclude(pk__in=all_ids)
            .values_list("pk", flat=True)
        )
        all_ids.update(pending_ids)

    return list(all_ids)


@require_GET
def search(request):
    from apps.theme_manager.models import TemplateType

    site_settings = SiteSettings.get_solo()
    template = _active_theme_template(
        site_settings.search_template,
        TemplateType.SEARCH_PAGE,
    )
    if template is None:
        raise Http404("Search template is not configured.")

    text_values = _query_values(request.GET, "text", "q", limit=5)
    title_values = _query_values(request.GET, "title", limit=5)
    tag_values = _query_values(request.GET, "tag")
    category_values = _query_values(request.GET, "category")
    author_values = _query_values(request.GET, "author")
    date_from_value = (request.GET.get("date_from") or "").strip()
    date_to_value = (request.GET.get("date_to") or "").strip()
    date_from = parse_date(date_from_value)
    date_to = parse_date(date_to_value)
    sort = (request.GET.get("sort") or "newest").strip().lower()
    has_filters = any(
        (
            text_values,
            title_values,
            tag_values,
            category_values,
            author_values,
            date_from,
            date_to,
        )
    )

    articles = (
        Article.objects
        .select_related("category", "author")
        .prefetch_related("tags")
        .filter(
            is_published=True,
            publish__lte=timezone.now(),
            category__isnull=False,
        )
    )

    for title_value in title_values:
        articles = articles.filter(title__icontains=title_value)

    for text_value in text_values:
        articles = articles.filter(
            Q(title__icontains=text_value)
            | Q(description__icontains=text_value)
            | Q(intro__icontains=text_value)
            | Q(body__icontains=text_value)
            | Q(keywords__icontains=text_value)
            | Q(tags__title__icontains=text_value)
            | Q(category__title__icontains=text_value)
        )

    if tag_values:
        tag_query = Q()
        for value in tag_values:
            tag_query |= Q(tags__slug__iexact=value) | Q(tags__title__iexact=value)
        articles = articles.filter(tag_query)

    if category_values:
        category_ids = _category_search_ids(category_values)
        articles = (
            articles.filter(category_id__in=category_ids)
            if category_ids
            else articles.none()
        )

    if author_values:
        author_query = Q()
        for value in author_values:
            author_query |= (
                Q(author__username__iexact=value)
                | Q(author__first_name__icontains=value)
                | Q(author__last_name__icontains=value)
            )
        articles = articles.filter(author_query)

    if date_from:
        articles = articles.filter(publish__date__gte=date_from)
    if date_to:
        articles = articles.filter(publish__date__lte=date_to)

    ordering = {
        "oldest": ("publish", "id"),
        "title": ("title", "id"),
        "newest": ("-publish", "-id"),
    }.get(sort, ("-publish", "-id"))
    sort = sort if sort in {"newest", "oldest", "title"} else "newest"
    articles = articles.distinct().order_by(*ordering) if has_filters else articles.none()

    paginator = Paginator(articles, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    preserved_query = request.GET.copy()
    preserved_query.pop("page", None)

    title = _("Search articles")
    description = _("Search published articles by text, tag, category, author, or date.")
    context = build_seo_context(request)
    context.update(
        {
            "title": title,
            "description": description,
            "robots": "noindex, follow",
            "noindex": True,
            "articles": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "results_count": paginator.count,
            "search_has_filters": has_filters,
            "search_text": " ".join(text_values),
            "search_title": " ".join(title_values),
            "search_tags": tag_values,
            "search_categories": category_values,
            "search_authors": author_values,
            "search_date_from": date_from_value,
            "search_date_to": date_to_value,
            "search_sort": sort,
            "search_querystring": preserved_query.urlencode(),
        }
    )

    return render(
        request,
        f"{template.theme.slug}/{template.slug}.html",
        context,
    )


def _plain_text(value, max_length=None):
    text = strip_tags(value or "").strip()

    if max_length:
        return text[:max_length]

    return text


def _php_form_error(message):
    return HttpResponse(message, content_type="text/plain")


@require_POST
def newsletter_subscribe(request):
    if (request.POST.get("website") or "").strip():
        return HttpResponse("OK", content_type="text/plain")

    site_settings = SiteSettings.get_solo()
    email = (request.POST.get("email") or "").strip().lower()
    source_url = (
        request.POST.get("source_url")
        or request.headers.get("Referer", "")
    )[:1000]

    try:
        forms.EmailField().clean(email)
    except forms.ValidationError:
        return HttpResponse("Please enter a valid email address.", status=400)

    ip_address = client_ip(request)
    request_limited = any(
        is_rate_limited(
            private_cache_key("newsletter-request", value),
            site_settings.newsletter_rate_limit,
            site_settings.newsletter_rate_window,
        )
        for value in (f"ip:{ip_address or 'unknown'}", f"email:{email}")
    )
    if request_limited:
        return HttpResponse(
            "Too many subscription requests. Please try again later.",
            status=429,
            content_type="text/plain",
        )

    subscription, created = NewsletterSubscription.objects.get_or_create(
        email=email,
        defaults={
            "is_active": not site_settings.newsletter_require_confirmation,
            "source_url": source_url,
            "ip_address": ip_address,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:1000],
        },
    )
    already_active = not created and subscription.is_active
    if not created:
        subscription.source_url = source_url
        subscription.ip_address = ip_address
        subscription.user_agent = request.META.get("HTTP_USER_AGENT", "")[:1000]
        if not site_settings.newsletter_require_confirmation:
            subscription.is_active = True
        subscription.save(
            update_fields=("source_url", "ip_address", "user_agent", "is_active", "updated_at")
        )

    if already_active:
        return HttpResponse(
            _("This email address is already subscribed."),
            content_type="text/plain",
        )

    if site_settings.newsletter_require_confirmation and not subscription.is_active:
        confirmation_limited = is_rate_limited(
            private_cache_key("newsletter-confirmation", email),
            site_settings.newsletter_confirmation_rate_limit,
            site_settings.newsletter_confirmation_rate_window,
        )
        if not confirmation_limited:
            token = signing.dumps(
                {"id": subscription.pk, "email": subscription.email},
                salt="core_manager.newsletter.confirm",
                compress=True,
            )
            confirmation_url = request.build_absolute_uri(
                reverse("core_manager:newsletter_confirm", args=[token])
            )
            try:
                send_mail(
                    _("Confirm your newsletter subscription"),
                    _("Confirm your subscription by opening this link: %(url)s")
                    % {"url": confirmation_url},
                    None,
                    [subscription.email],
                    fail_silently=False,
                )
            except Exception:
                # Keep the public response generic while leaving an actionable
                # server-side error for the administrator.
                logger.exception("Could not send newsletter confirmation email")

    message = (
        _("We have sent a confirmation link to your email address.")
        if site_settings.newsletter_require_confirmation
        else _("You have successfully subscribed to the newsletter.")
    )
    return HttpResponse(message, content_type="text/plain")


@require_GET
def newsletter_confirm(request, token):
    site_settings = SiteSettings.get_solo()
    try:
        payload = signing.loads(
            token,
            salt="core_manager.newsletter.confirm",
            max_age=site_settings.newsletter_confirmation_token_ttl,
        )
    except (signing.BadSignature, signing.SignatureExpired):
        return HttpResponse(
            "This confirmation link is invalid or has expired.",
            status=400,
            content_type="text/plain",
        )

    updated = NewsletterSubscription.objects.filter(
        pk=payload.get("id"),
        email=payload.get("email"),
    ).update(is_active=True)
    if not updated:
        return HttpResponse(
            "This confirmation link is invalid or has expired.",
            status=400,
            content_type="text/plain",
        )
    return HttpResponse("Subscription confirmed.", content_type="text/plain")


@require_POST
def contact_send(request):
    if (request.POST.get("website") or "").strip():
        return HttpResponse("OK", content_type="text/plain")

    name = _plain_text(request.POST.get("name"), 255)
    email = (request.POST.get("email") or "").strip().lower()
    subject = _plain_text(request.POST.get("subject"), 255)
    site_settings = SiteSettings.get_solo()
    raw_message = request.POST.get("message") or ""
    if len(raw_message) > site_settings.contact_message_max_length:
        return _php_form_error("The message is too long.")
    message = _plain_text(raw_message, site_settings.contact_message_max_length)
    source_url = (
        request.POST.get("source_url")
        or request.headers.get("Referer", "")
    )[:1000]
    ip_address = client_ip(request)

    try:
        forms.EmailField().clean(email)
    except forms.ValidationError:
        return _php_form_error("Please enter a valid email address.")

    if not name:
        return _php_form_error("Please enter your name.")
    if not subject:
        return _php_form_error("Please enter a subject.")
    if len(message) < 3:
        return _php_form_error("Please enter a longer message.")

    rate_limited = any(
        is_rate_limited(
            private_cache_key("contact-message", value),
            site_settings.contact_rate_limit,
            site_settings.contact_rate_window,
        )
        for value in (f"ip:{ip_address or 'unknown'}", f"email:{email}")
    )
    if rate_limited:
        return _php_form_error("Too many messages. Please try again later.")

    ContactMessage.objects.create(
        name=name,
        email=email,
        subject=subject,
        message=message,
        source_url=source_url,
        ip_address=ip_address,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
    )

    return HttpResponse("OK", content_type="text/plain")


def _template_name(template):
    if not template:
        raise Http404("Template is not configured.")

    return f"{template.theme.slug}/{template.slug}.html"


def home(request):
    page = (
        SiteSettings.get_solo()
        .home_page
    )

    if not page or not page.is_published:
        raise Http404("Home page is not configured.")

    context = {
        "menu_item": None,
        "page": page,
        "title": page.title,
    }
    context.update(
        build_seo_context(
            request,
            page=page,
        )
    )

    return render(
        request,
        _template_name(page.template),
        context,
    )


def slug_detail(request, slug):
    page = (
        Page.objects.select_related("template", "template__theme")
        .filter(
            slug=slug,
            is_published=True,
        )
        .first()
    )

    if page:
        homepage = SiteSettings.get_solo().home_page
        if homepage and homepage.pk == page.pk:
            return redirect("core_manager:home", permanent=True)

        context = {
            "menu_item": None,
            "page": page,
            "title": page.title,
        }
        context.update(
            build_seo_context(
                request,
                page=page,
            )
        )

        return render(
            request,
            _template_name(page.template),
            context,
        )

    return BlogCategoryView.as_view()(request, category_slug=slug)


def item_detail(request, category_slug, item_slug):
    return BlogArticleView.as_view()(
        request,
        category_slug=category_slug,
        post_slug=item_slug,
    )
