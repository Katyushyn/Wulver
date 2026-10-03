from io import BytesIO
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .forms import PageAdminForm, SiteSettingsAdminForm
from .image_processing import (
    FAVICON_ICO_SPEC,
    SOCIAL_PREVIEW_SPEC,
    process_uploaded_image,
)
from .models import ContactMessage, NewsletterSubscription, SiteSettings
from .middleware import ContentSecurityPolicyMiddleware
from .seo import build_seo_context, get_canonical_url
from apps.theme_manager.models import TemplateType, Theme, ThemeTemplate
from apps.blog_manager.models import Article, Category, Tag


def make_uploaded_image(size, image_format="PNG"):
    output = BytesIO()
    Image.new("RGB", size, "#f5c518").save(output, format=image_format)
    extension = image_format.lower().replace("jpeg", "jpg")

    return SimpleUploadedFile(
        f"source.{extension}",
        output.getvalue(),
        content_type=f"image/{image_format.lower()}",
    )


class CanonicalUrlTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def canonical(self, path):
        request = self.factory.get(path, HTTP_HOST="testserver")
        return get_canonical_url(request, "page,tag,text,sort")

    def test_page_one_uses_clean_url(self):
        self.assertEqual(
            self.canonical("/category/?page=1"),
            "http://testserver/category/",
        )
        self.assertEqual(
            self.canonical("/category/?page=01&tag=django"),
            "http://testserver/category/",
        )

    def test_later_page_is_preserved_when_it_is_the_only_parameter(self):
        self.assertEqual(
            self.canonical("/category/?page=3"),
            "http://testserver/category/?page=3",
        )

    def test_page_is_removed_when_any_filter_is_present(self):
        self.assertEqual(
            self.canonical("/category/?tag=django&sort=oldest&page=3"),
            "http://testserver/category/",
        )
        self.assertEqual(
            self.canonical("/search/?tag=codex&page=3"),
            "http://testserver/search/",
        )
        self.assertEqual(
            self.canonical("/search/?tag=&page=3"),
            "http://testserver/search/",
        )

    def test_search_filters_use_the_clean_search_canonical(self):
        self.assertEqual(
            self.canonical("/search/?tag=codex&text=django&sort=title"),
            "http://testserver/search/",
        )

    def test_invalid_or_repeated_page_is_removed(self):
        self.assertEqual(
            self.canonical("/category/?page=invalid"),
            "http://testserver/category/",
        )
        self.assertEqual(
            self.canonical("/category/?page=2&page=3"),
            "http://testserver/category/",
        )


class ContentSecurityPolicyTests(SimpleTestCase):
    @override_settings(
        CSP_ENABLED=True,
        CSP_REPORT_ONLY=False,
        CSP_POLICY="default-src 'self'; object-src 'none'",
        CSP_ADMIN_POLICY="default-src 'self'; script-src 'self' 'unsafe-eval'",
    )
    def test_enforced_header_is_added(self):
        middleware = ContentSecurityPolicyMiddleware(
            lambda request: HttpResponse("OK")
        )

        response = middleware(RequestFactory().get("/"))

        self.assertEqual(
            response["Content-Security-Policy"],
            "default-src 'self'; object-src 'none'",
        )

    @override_settings(
        CSP_ENABLED=True,
        CSP_REPORT_ONLY=False,
        CSP_POLICY="script-src 'self'",
        CSP_ADMIN_POLICY="script-src 'self' 'unsafe-eval'",
    )
    def test_admin_uses_unfold_compatible_policy(self):
        middleware = ContentSecurityPolicyMiddleware(
            lambda request: HttpResponse("OK")
        )

        for path in ("/admin/", "/uk/admin/blog_manager/article/"):
            with self.subTest(path=path):
                response = middleware(RequestFactory().get(path))
                self.assertEqual(
                    response["Content-Security-Policy"],
                    "script-src 'self' 'unsafe-eval'",
                )

    @override_settings(
        CSP_ENABLED=True,
        CSP_REPORT_ONLY=False,
        CSP_POLICY="script-src 'self'",
        CSP_ADMIN_POLICY="script-src 'self' 'unsafe-eval'",
    )
    def test_public_page_keeps_strict_policy(self):
        middleware = ContentSecurityPolicyMiddleware(
            lambda request: HttpResponse("OK")
        )

        response = middleware(RequestFactory().get("/articles/example/"))

        self.assertEqual(response["Content-Security-Policy"], "script-src 'self'")


class ImageProcessingTests(SimpleTestCase):
    def test_social_preview_is_cropped_and_saved_as_jpeg(self):
        result = process_uploaded_image(
            make_uploaded_image((1600, 1000)),
            SOCIAL_PREVIEW_SPEC,
        )

        with Image.open(result) as image:
            self.assertEqual(image.size, (1200, 630))
            self.assertEqual(image.format, "JPEG")

    def test_avif_upload_is_accepted_and_converted(self):
        result = process_uploaded_image(
            make_uploaded_image((1600, 1000), image_format="AVIF"),
            SOCIAL_PREVIEW_SPEC,
        )

        with Image.open(result) as image:
            self.assertEqual(image.size, (1200, 630))
            self.assertEqual(image.format, "JPEG")

    def test_image_smaller_than_minimum_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Image must be at least 1200 x 630 px",
        ):
            process_uploaded_image(
                make_uploaded_image((1199, 630)),
                SOCIAL_PREVIEW_SPEC,
            )

    def test_favicon_is_saved_as_ico(self):
        result = process_uploaded_image(
            make_uploaded_image((512, 512)),
            FAVICON_ICO_SPEC,
        )

        with Image.open(result) as image:
            self.assertEqual(image.size, (48, 48))
            self.assertEqual(image.format, "ICO")

    def test_admin_forms_describe_image_requirements(self):
        site_form = SiteSettingsAdminForm()
        page_form = PageAdminForm()

        self.assertIn(
            "1200 x 630",
            site_form.fields["default_preview_image"].help_text,
        )
        self.assertIn(
            "multi-size ICO",
            site_form.fields["favicon_ico"].help_text,
        )
        self.assertIn(
            "Organization logo",
            site_form.fields["organization_logo"].help_text,
        )
        self.assertIn(
            "Person image",
            site_form.fields["person_image"].help_text,
        )
        self.assertIn(
            "1200 x 630",
            page_form.fields["preview_image"].help_text,
        )


class SEOContextTests(TestCase):
    def test_schema_json_cannot_close_its_script_element(self):
        site_settings = SiteSettings.get_solo()
        site_settings.default_schema_graph = {
            "name": "</script><script>alert(1)</script>&"
        }
        site_settings.save(update_fields=["default_schema_graph"])
        request = RequestFactory().get("/", HTTP_HOST="localhost")

        schema = str(build_seo_context(request)["schema_graph"])

        self.assertNotIn("</script", schema.lower())
        self.assertIn(r"\u003C/script\u003E", schema)
        self.assertIn(r"\u0026", schema)

    def test_locale_and_site_url_follow_active_language_and_site_settings(self):
        site_settings = SiteSettings.get_solo()
        site_settings.site_url = "https://example.com/"
        site_settings.save(update_fields=["site_url"])
        request = RequestFactory().get("/", HTTP_HOST="localhost")
        request.LANGUAGE_CODE = "en"

        context = build_seo_context(request)

        self.assertEqual(context["lang"], "en")
        self.assertEqual(context["og_locale"], "en_US")
        self.assertEqual(context["base_url"], "https://example.com")

        request.LANGUAGE_CODE = "uk"
        self.assertEqual(build_seo_context(request)["og_locale"], "uk_UA")

    def test_favicon_is_not_used_as_social_preview(self):
        site_settings = SiteSettings.get_solo()
        site_settings.favicon_png = "core/settings/favicons/favicon.png"
        site_settings.save(update_fields=["favicon_png"])
        request = RequestFactory().get("/", HTTP_HOST="localhost")

        context = build_seo_context(request)

        self.assertEqual(context["preview"], "")
        self.assertEqual(context["preview_url"], "")

    def test_schema_uses_distinct_organization_and_person_images(self):
        site_settings = SiteSettings.get_solo()
        site_settings.organization_name = "Example Organization"
        site_settings.organization_logo = "schema/organization/logo.png"
        site_settings.person_name = "Example Person"
        site_settings.person_image = "schema/person/portrait.png"
        site_settings.save(
            update_fields=[
                "organization_name",
                "organization_logo",
                "person_name",
                "person_image",
            ]
        )
        request = RequestFactory().get("/", HTTP_HOST="localhost")

        graph = build_seo_context(request)["schema_graph_data"]["@graph"]
        organization = next(
            item for item in graph if item["@type"] == "Organization"
        )
        person = next(item for item in graph if item["@type"] == "Person")

        self.assertTrue(organization["logo"]["url"].endswith("/logo.png"))
        self.assertTrue(person["image"].endswith("/portrait.png"))

    def test_title_and_description_use_content_before_settings(self):
        site_settings = SiteSettings.get_solo()
        site_settings.title = "Settings title"
        site_settings.description = "Settings description"
        site_settings.save()
        request = RequestFactory().get("/", HTTP_HOST="localhost")
        content = SimpleNamespace(
            title="Article title",
            description="Article description",
            keywords="recovery, ukraine",
        )

        context = build_seo_context(
            request,
            page=content,
        )

        self.assertEqual(context["title"], "Article title")
        self.assertEqual(context["description"], "Article description")
        self.assertEqual(context["keywords"], "recovery, ukraine")

    def test_empty_content_uses_settings(self):
        site_settings = SiteSettings.get_solo()
        site_settings.title = "Settings title"
        site_settings.description = "Settings description"
        site_settings.save()
        request = RequestFactory().get("/", HTTP_HOST="localhost")
        empty_content = SimpleNamespace(title=" ", description="", keywords="")
        content = SimpleNamespace(
            title="Article title",
            description="Article description",
            keywords="",
        )

        content_context = build_seo_context(
            request,
            page=content,
        )
        settings_context = build_seo_context(
            request,
            page=empty_content,
        )

        self.assertEqual(content_context["title"], "Article title")
        self.assertEqual(content_context["description"], "Article description")
        self.assertEqual(settings_context["title"], "Settings title")
        self.assertEqual(settings_context["description"], "Settings description")



class Error404Tests(TestCase):
    def test_active_error_template_is_rendered_with_404_status(self):
        theme = Theme.objects.create(name="Error theme", slug="error-theme")
        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.ERROR_TEMPLATE,
            name="404",
            slug="404",
        )
        site_settings = SiteSettings.get_solo()
        site_settings.error_404_template = template
        site_settings.save(update_fields=["error_404_template"])
        request = RequestFactory().get("/missing/", HTTP_HOST="localhost")

        with patch("apps.core_manager.views.render") as mocked_render:
            mocked_render.return_value = HttpResponse(status=404)

            from .views import page_not_found

            response = page_not_found(request, Http404())

        self.assertEqual(response.status_code, 404)
        args, kwargs = mocked_render.call_args
        self.assertEqual(args[1], "error-theme/404.html")
        self.assertEqual(args[2]["error_code"], 404)
        self.assertEqual(args[2]["title"], "Page not found")
        self.assertEqual(args[2]["robots"], "noindex, nofollow")
        self.assertEqual(args[2]["canonical_url"], "")
        self.assertEqual(args[2]["alternate_links"], "")
        self.assertTrue(args[2]["is_error_page"])
        self.assertEqual(kwargs["status"], 404)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_default_404_template_has_no_indexable_or_stale_metadata(self):
        theme = Theme.objects.create(
            name="Sample theme",
            slug="sample-theme",
            is_active=True,
        )
        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.ERROR_TEMPLATE,
            name="404",
            slug="404",
            is_active=True,
        )
        site_settings = SiteSettings.get_solo()
        site_settings.error_404_template = template
        site_settings.title = "Ukraine Recovery Initiative"
        site_settings.og_site_name = "Example Site"
        site_settings.save()
        request = RequestFactory().get("/missing/", HTTP_HOST="localhost")

        from .views import page_not_found

        response = page_not_found(request, Http404())
        content = response.content.decode()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("<title>Page not found</title>", content)
        self.assertIn(
            '<meta name="robots" content="noindex, nofollow">',
            content,
        )
        self.assertNotIn('rel="canonical"', content)
        self.assertNotIn("Ukraine Recovery Initiative", content)
        self.assertNotIn("Example Site", content)

    def test_active_theme_error_template_is_used_when_setting_is_empty(self):
        theme = Theme.objects.create(
            name="Active error theme",
            slug="active-error-theme",
            is_active=True,
        )
        ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.ERROR_TEMPLATE,
            name="404",
            slug="404",
        )
        request = RequestFactory().get("/missing/", HTTP_HOST="localhost")

        with patch("apps.core_manager.views.render") as mocked_render:
            mocked_render.return_value.status_code = 404

            from .views import page_not_found

            response = page_not_found(request, Http404())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(mocked_render.call_args.args[1], "active-error-theme/404.html")

    def test_missing_error_template_uses_plain_404_fallback(self):
        request = RequestFactory().get("/missing/", HTTP_HOST="localhost")

        from .views import page_not_found

        response = page_not_found(request, Http404())

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "404", status_code=404)
        self.assertContains(
            response,
            '<meta name="robots" content="noindex, nofollow">',
            status_code=404,
            html=True,
        )
        self.assertNotContains(response, 'rel="canonical"', status_code=404)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")


class SearchViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.theme = Theme.objects.create(
            name="Search theme",
            slug="search-theme",
            is_active=True,
        )
        cls.template = ThemeTemplate.objects.create(
            theme=cls.theme,
            template_type=TemplateType.SEARCH_PAGE,
            name="Search",
            slug="search",
        )
        cls.parent_category = Category.objects.create(
            title="Development",
            slug="development",
            description="Development articles",
        )
        cls.child_category = Category.objects.create(
            parent=cls.parent_category,
            title="Django",
            slug="django",
            description="Django articles",
        )
        cls.other_category = Category.objects.create(
            title="Design",
            slug="design",
            description="Design articles",
        )
        cls.python_tag = Tag.objects.create(title="Python", slug="python")
        cls.css_tag = Tag.objects.create(title="CSS", slug="css")

        cls.matching_article = Article.objects.create(
            title="Universal Django CMS",
            slug="universal-django-cms",
            description="A flexible publishing system",
            intro="Django publishing",
            body="Reusable CMS architecture",
            category=cls.child_category,
            publish=timezone.now() - timedelta(days=2),
        )
        cls.matching_article.tags.add(cls.python_tag)

        cls.wrong_tag_article = Article.objects.create(
            title="Django interface",
            slug="django-interface",
            description="A design article",
            intro="Django styled with CSS",
            body="Interface details",
            category=cls.child_category,
            publish=timezone.now() - timedelta(days=1),
        )
        cls.wrong_tag_article.tags.add(cls.css_tag)

        cls.unpublished_article = Article.objects.create(
            title="Hidden Django CMS",
            slug="hidden-django-cms",
            description="Hidden",
            intro="Hidden",
            body="Hidden",
            category=cls.child_category,
            is_published=False,
        )

    def setUp(self):
        settings = SiteSettings.get_solo()
        settings.search_template = self.template
        settings.save(update_fields=["search_template"])

    def test_combined_filters_use_and_and_include_child_categories(self):
        request = RequestFactory().get(
            "/search/",
            {
                "text": "Django",
                "tag": "python",
                "category": "development",
            },
            HTTP_HOST="localhost",
        )

        with patch("apps.core_manager.views.render") as mocked_render:
            from .views import search

            search(request)

        template_name = mocked_render.call_args.args[1]
        context = mocked_render.call_args.args[2]
        self.assertEqual(template_name, "search-theme/search.html")
        self.assertEqual(list(context["articles"]), [self.matching_article])
        self.assertEqual(context["results_count"], 1)
        self.assertTrue(context["noindex"])
        self.assertIn("text=Django", context["search_querystring"])
        self.assertIn("tag=python", context["search_querystring"])
        self.assertNotIn("page=", context["search_querystring"])

    def test_empty_search_does_not_return_every_article(self):
        request = RequestFactory().get("/search/", HTTP_HOST="localhost")

        with patch("apps.core_manager.views.render") as mocked_render:
            from .views import search

            search(request)

        context = mocked_render.call_args.args[2]
        self.assertEqual(context["results_count"], 0)
        self.assertFalse(context["search_has_filters"])

    def test_q_alias_and_sort_are_supported(self):
        request = RequestFactory().get(
            "/search/",
            {"q": "interface", "sort": "oldest"},
            HTTP_HOST="localhost",
        )

        with patch("apps.core_manager.views.render") as mocked_render:
            from .views import search

            search(request)

        context = mocked_render.call_args.args[2]
        self.assertEqual(list(context["articles"]), [self.wrong_tag_article])
        self.assertEqual(context["search_text"], "interface")
        self.assertEqual(context["search_sort"], "oldest")

    def test_active_search_template_is_fallback_when_setting_is_empty(self):
        settings = SiteSettings.get_solo()
        settings.search_template = None
        settings.save(update_fields=["search_template"])
        request = RequestFactory().get(
            "/search/",
            {"tag": "python"},
            HTTP_HOST="localhost",
        )

        with patch("apps.core_manager.views.render") as mocked_render:
            from .views import search

            search(request)

        self.assertEqual(mocked_render.call_args.args[1], "search-theme/search.html")

    def test_search_route_precedes_dynamic_slug_route(self):
        self.assertEqual(reverse("core_manager:search"), "/search/")


class AdminImageUploadTests(TestCase):
    def test_page_admin_form_accepts_avif_upload(self):
        form = PageAdminForm(
            data={
                "title": "AVIF page",
                "slug": "avif-page",
                "description": "AVIF page description",
                "content": "",
                "template": "",
                "is_published": "on",
                "og_type": "website",
                "schema_graph": "{}",
            },
            files={
                "preview_image": make_uploaded_image(
                    (1600, 1000),
                    image_format="AVIF",
                ),
            },
        )

        self.assertTrue(form.is_valid(), form.errors.as_text())

        with Image.open(form.cleaned_data["preview_image"]) as image:
            self.assertEqual(image.size, (1200, 630))
            self.assertEqual(image.format, "JPEG")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NewsletterSubscriptionTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_subscribe_creates_subscription(self):
        response = self.client.post(
            reverse("core_manager:newsletter_subscribe"),
            {"email": "User@Example.COM"},
            HTTP_REFERER="https://example.com/home/",
            HTTP_USER_AGENT="Test browser",
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content.decode(),
            "We have sent a confirmation link to your email address.",
        )

        subscription = NewsletterSubscription.objects.get()
        self.assertEqual(subscription.email, "user@example.com")
        self.assertFalse(subscription.is_active)
        self.assertEqual(subscription.source_url, "https://example.com/home/")
        self.assertEqual(subscription.ip_address, "127.0.0.1")
        self.assertEqual(subscription.user_agent, "Test browser")
        self.assertEqual(len(mail.outbox), 1)

        confirmation_url = mail.outbox[0].body.rsplit(" ", 1)[-1]
        confirmation_response = self.client.get(confirmation_url)
        subscription.refresh_from_db()
        self.assertEqual(confirmation_response.status_code, 200)
        self.assertTrue(subscription.is_active)

    def test_subscribe_updates_existing_subscription(self):
        NewsletterSubscription.objects.create(
            email="user@example.com",
            is_active=False,
        )

        response = self.client.post(
            reverse("core_manager:newsletter_subscribe"),
            {"email": "user@example.com"},
            HTTP_REFERER="https://example.com/footer/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(NewsletterSubscription.objects.count(), 1)

        subscription = NewsletterSubscription.objects.get()
        self.assertFalse(subscription.is_active)
        self.assertEqual(subscription.source_url, "https://example.com/footer/")

    def test_subscribe_does_not_deactivate_confirmed_subscription(self):
        NewsletterSubscription.objects.create(
            email="user@example.com",
            is_active=True,
        )

        response = self.client.post(
            reverse("core_manager:newsletter_subscribe"),
            {"email": "user@example.com"},
        )

        self.assertEqual(
            response.content.decode(),
            "This email address is already subscribed.",
        )
        self.assertTrue(
            NewsletterSubscription.objects.get(email="user@example.com").is_active
        )

    def test_subscribe_honeypot_is_silently_ignored(self):
        response = self.client.post(
            reverse("core_manager:newsletter_subscribe"),
            {"email": "bot@example.com", "website": "https://spam.example"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(NewsletterSubscription.objects.exists())

    def test_subscribe_rate_limits_ip_and_email(self):
        settings = SiteSettings.get_solo()
        settings.newsletter_rate_limit = 1
        settings.save(update_fields=["newsletter_rate_limit"])

        first = self.client.post(
            reverse("core_manager:newsletter_subscribe"),
            {"email": "first@example.com"},
            REMOTE_ADDR="127.0.0.1",
        )
        second = self.client.post(
            reverse("core_manager:newsletter_subscribe"),
            {"email": "second@example.com"},
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    def test_subscribe_rejects_invalid_email(self):
        response = self.client.post(
            reverse("core_manager:newsletter_subscribe"),
            {"email": "not-an-email"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(NewsletterSubscription.objects.count(), 0)


class ContactMessageTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_contact_send_creates_plain_text_message(self):
        response = self.client.post(
            reverse("core_manager:contact_send"),
            {
                "name": "<b>Alice</b>",
                "email": "Alice@Example.COM",
                "subject": "<em>Hello</em>",
                "message": "<script>alert(1)</script>Hello from the website.",
            },
            HTTP_REFERER="https://example.com/contact/",
            HTTP_USER_AGENT="Test browser",
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "OK")

        message = ContactMessage.objects.get()
        self.assertEqual(message.name, "Alice")
        self.assertEqual(message.email, "alice@example.com")
        self.assertEqual(message.subject, "Hello")
        self.assertNotIn("<script>", message.message)
        self.assertIn("Hello from the website.", message.message)
        self.assertFalse(message.is_read)
        self.assertEqual(message.source_url, "https://example.com/contact/")
        self.assertEqual(message.ip_address, "127.0.0.1")
        self.assertEqual(message.user_agent, "Test browser")

    @override_settings(TRUST_X_FORWARDED_FOR=False)
    def test_contact_ignores_untrusted_forwarded_for(self):
        self.client.post(
            reverse("core_manager:contact_send"),
            {
                "name": "Alice",
                "email": "alice@example.com",
                "subject": "Hello",
                "message": "This is a normal contact message.",
            },
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_FORWARDED_FOR="203.0.113.50",
        )

        self.assertEqual(ContactMessage.objects.get().ip_address, "127.0.0.1")

    def test_contact_send_ignores_honeypot_submission(self):
        response = self.client.post(
            reverse("core_manager:contact_send"),
            {
                "name": "Bot",
                "email": "bot@example.com",
                "subject": "Spam",
                "message": "This should not be stored.",
                "website": "https://spam.example",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "OK")
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_contact_send_rejects_short_message(self):
        response = self.client.post(
            reverse("core_manager:contact_send"),
            {
                "name": "Alice",
                "email": "alice@example.com",
                "subject": "Hello",
                "message": "Hi",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Please enter a longer message.")
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_contact_send_rate_limits_by_ip_and_email(self):
        payload = {
            "name": "Alice",
            "email": "alice@example.com",
            "subject": "Hello",
            "message": "This is a normal contact message.",
        }

        for _index in range(5):
            response = self.client.post(
                reverse("core_manager:contact_send"),
                payload,
                REMOTE_ADDR="127.0.0.1",
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("core_manager:contact_send"),
            payload,
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content.decode(),
            "Too many messages. Please try again later.",
        )
        self.assertEqual(ContactMessage.objects.count(), 5)

# Create your tests here.
