from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.blog_manager.models import Article, Category

from .middleware import URLRedirectMiddleware
from .models import Page, URLRedirect
from .redirects import register_redirect


class URLRedirectModelTests(TestCase):
    def test_normalizes_local_paths(self):
        redirect = URLRedirect.objects.create(
            old_path="old-page/",
            target_url="new-page/",
        )

        self.assertEqual(redirect.old_path, "/old-page/")
        self.assertEqual(redirect.target_url, "/new-page/")

    def test_rejects_external_old_path_and_self_redirect(self):
        with self.assertRaises(ValidationError):
            URLRedirect.objects.create(
                old_path="https://example.com/old/",
                target_url="/new/",
            )
        with self.assertRaises(ValidationError):
            URLRedirect.objects.create(
                old_path="/same/",
                target_url="/same/",
            )

    def test_automatic_redirects_collapse_previous_chain(self):
        register_redirect("/first/", "/second/")
        register_redirect("/second/", "/third/")

        self.assertEqual(
            URLRedirect.objects.get(old_path="/first/").target_url,
            "/third/",
        )
        self.assertEqual(
            URLRedirect.objects.get(old_path="/second/").target_url,
            "/third/",
        )


class URLRedirectMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_redirects_only_after_404_and_updates_statistics(self):
        redirect = URLRedirect.objects.create(
            old_path="/old-address/",
            target_url="/new-address/",
        )
        middleware = URLRedirectMiddleware(lambda _request: HttpResponse(status=404))

        response = middleware(self.factory.get("/old-address/?utm_source=test"))

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/new-address/")
        redirect.refresh_from_db()
        self.assertEqual(redirect.hit_count, 1)
        self.assertIsNotNone(redirect.last_used_at)

    def test_accepts_old_path_without_trailing_slash(self):
        URLRedirect.objects.create(
            old_path="/old-address/",
            target_url="/new-address/",
        )
        middleware = URLRedirectMiddleware(lambda _request: HttpResponse(status=404))

        response = middleware(self.factory.get("/old-address"))

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/new-address/")

    def test_does_not_override_a_valid_page(self):
        URLRedirect.objects.create(old_path="/current/", target_url="/other/")
        middleware = URLRedirectMiddleware(lambda _request: HttpResponse("Current"))

        response = middleware(self.factory.get("/current/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Current")

    def test_ignores_admin_static_and_media_404_responses(self):
        middleware = URLRedirectMiddleware(lambda _request: HttpResponse(status=404))
        for path in ("/admin/missing/", "/uk/admin/missing/", "/static/missing.css", "/media/missing.jpg"):
            URLRedirect.objects.create(old_path=path, target_url="/other/")
            self.assertEqual(middleware(self.factory.get(path)).status_code, 404)


class AutomaticURLRedirectTests(TestCase):
    def test_page_slug_change_creates_all_language_redirects(self):
        page = Page.objects.create(
            title="Old page",
            slug="old-page",
            description="Page",
        )

        page.slug = "new-page"
        page.save(update_fields=["slug"])

        self.assertEqual(
            URLRedirect.objects.get(old_path="/old-page/").target_url,
            "/new-page/",
        )
        self.assertEqual(
            URLRedirect.objects.get(old_path="/uk/old-page/").target_url,
            "/uk/new-page/",
        )

    def test_article_slug_or_category_change_creates_redirects(self):
        first = Category.objects.create(
            title="First",
            slug="first",
            description="First category",
        )
        second = Category.objects.create(
            title="Second",
            slug="second",
            description="Second category",
        )
        article = Article.objects.create(
            title="Article",
            slug="old-article",
            description="Article",
            intro="Intro",
            body="Body",
            category=first,
        )

        article.slug = "new-article"
        article.category = second
        article.save(update_fields=["slug", "category"])

        self.assertEqual(
            URLRedirect.objects.get(old_path="/first/old-article/").target_url,
            "/second/new-article/",
        )
        self.assertEqual(
            URLRedirect.objects.get(old_path="/uk/first/old-article/").target_url,
            "/uk/second/new-article/",
        )

    def test_category_slug_change_redirects_category_and_its_articles(self):
        category = Category.objects.create(
            title="Category",
            slug="old-category",
            description="Category",
        )
        Article.objects.create(
            title="Article",
            slug="article",
            description="Article",
            intro="Intro",
            body="Body",
            category=category,
        )

        category.slug = "new-category"
        category.save(update_fields=["slug"])

        self.assertEqual(
            URLRedirect.objects.get(old_path="/old-category/").target_url,
            "/new-category/",
        )
        self.assertEqual(
            URLRedirect.objects.get(old_path="/old-category/article/").target_url,
            "/new-category/article/",
        )
