from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.blog_manager.models import Article, Category
from apps.theme_manager.models import TemplateType, Theme, ThemeTemplate

from .models import Page, SitemapSettings, SiteSettings


class SitemapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.theme = Theme.objects.create(
            name="Sitemap theme",
            slug="sitemap-theme",
            is_active=True,
        )
        cls.page_template = ThemeTemplate.objects.create(
            theme=cls.theme,
            template_type=TemplateType.PARENT_PAGE,
            name="Page",
            slug="page",
            is_active=True,
        )
        cls.technical_template = ThemeTemplate.objects.create(
            theme=cls.theme,
            template_type=TemplateType.INCLUDE_BLOCK,
            name="Header",
            slug="header",
            is_active=True,
        )
        cls.search_template = ThemeTemplate.objects.create(
            theme=cls.theme,
            template_type=TemplateType.SEARCH_PAGE,
            name="Search",
            slug="search",
            is_active=True,
        )
        cls.homepage = Page.objects.create(
            title="Home",
            title_en="Home",
            title_uk="Головна",
            slug="home",
            template=cls.page_template,
            description="Homepage",
            description_en="Homepage",
            description_uk="Головна сторінка",
            is_published=True,
        )
        cls.page_template_2 = ThemeTemplate.objects.create(
            theme=cls.theme,
            template_type=TemplateType.PARENT_PAGE,
            name="About page",
            slug="about-page",
            is_active=True,
        )
        cls.about = Page.objects.create(
            title="About",
            title_en="About",
            title_uk="Про нас",
            slug="about",
            template=cls.page_template_2,
            description="About page",
            description_en="About page",
            description_uk="Сторінка про нас",
            is_published=True,
        )
        cls.technical_page = Page.objects.create(
            title="Technical",
            slug="technical",
            template=cls.technical_template,
            description="Must not appear",
            is_published=True,
        )
        cls.hidden_page_template = ThemeTemplate.objects.create(
            theme=cls.theme,
            template_type=TemplateType.PARENT_PAGE,
            name="Hidden page",
            slug="hidden-page",
            is_active=True,
        )
        cls.hidden_page = Page.objects.create(
            title="Hidden",
            slug="hidden",
            template=cls.hidden_page_template,
            description="Noindex",
            is_published=True,
            noindex=True,
        )
        site_settings = SiteSettings.get_solo()
        site_settings.home_page = cls.homepage
        site_settings.search_template = cls.search_template
        site_settings.site_url = "https://example.com"
        site_settings.robots_txt = "User-agent: *\nDisallow: /admin/"
        site_settings.save()

        cls.category = Category.objects.create(
            title="Development",
            title_en="Development",
            title_uk="Розробка",
            slug="development",
            description="Development articles",
            description_en="Development articles",
            description_uk="Статті про розробку",
        )
        cls.noindex_category = Category.objects.create(
            title="Private",
            slug="private",
            description="Private articles",
            noindex=True,
        )
        cls.article = Article.objects.create(
            title="Public article",
            title_en="Public article",
            title_uk="Публічна стаття",
            slug="public-article",
            description="Public article description",
            description_en="Public article description",
            description_uk="Опис публічної статті",
            intro="Intro",
            intro_en="Intro",
            intro_uk="Вступ",
            body="Body",
            body_en="Body",
            body_uk="Текст",
            category=cls.category,
            is_published=True,
            publish=timezone.now() - timedelta(days=1),
        )
        cls.future_article = Article.objects.create(
            title="Future article",
            slug="future-article",
            description="Future",
            intro="Future",
            body="Future",
            category=cls.category,
            is_published=True,
            publish=timezone.now() + timedelta(days=1),
        )
        SitemapSettings.objects.update_or_create(
            pk=1,
            defaults={
                "include_translations": False,
                "include_alternates": False,
                "cache_timeout": 0,
            },
        )

    def test_primary_sitemap_contains_all_configured_public_content(self):
        response = self.client.get(reverse("sitemap-index"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("http://testserver/</loc>", content)
        self.assertIn("http://testserver/about/", content)
        self.assertIn("http://testserver/development/", content)
        self.assertIn("http://testserver/development/public-article/", content)
        self.assertNotIn("/tag/", content)
        self.assertNotIn("/sitemaps/", content)
        self.assertNotIn("templates.xml", content)
        self.assertIn('<?xml-stylesheet type="text/xsl" href="/sitemap.xsl"?>', content)

    def test_sitemap_stylesheet_is_available(self):
        response = self.client.get(reverse("sitemap-stylesheet"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/xsl; charset=utf-8")
        self.assertContains(response, "Last modified")
        self.assertContains(response, "Priority")

    def test_pages_include_page_records_but_not_technical_templates(self):
        response = self.client.get(
            reverse("sitemap-section", kwargs={"section": "pages"})
        )
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("http://testserver/about/", content)
        self.assertNotIn("/technical/", content)
        self.assertNotIn("/hidden/", content)
        self.assertNotIn("http://testserver/</loc>", content)
        self.assertIn("<priority>0.8</priority>", content)

    def test_homepage_articles_and_categories_use_requested_priorities(self):
        expectations = {
            "homepage": ("http://testserver/", "1.0"),
            "categories": ("/development/", "0.8"),
            "articles": ("/development/public-article/", "0.7"),
        }
        for section, (url_fragment, priority) in expectations.items():
            with self.subTest(section=section):
                response = self.client.get(
                    reverse("sitemap-section", kwargs={"section": section})
                )
                content = response.content.decode()
                self.assertIn(url_fragment, content)
                self.assertIn(f"<priority>{priority}</priority>", content)

        article_xml = self.client.get(
            reverse("sitemap-section", kwargs={"section": "articles"})
        ).content.decode()
        self.assertNotIn("future-article", article_xml)

    def test_multilingual_urls_and_alternates_are_generated(self):
        configuration = SitemapSettings.get_solo()
        configuration.include_translations = True
        configuration.include_alternates = True
        configuration.save()

        response = self.client.get(
            reverse("sitemap-section", kwargs={"section": "articles"})
        )
        content = response.content.decode()

        self.assertIn("http://testserver/development/public-article/", content)
        self.assertIn("http://testserver/uk/development/public-article/", content)
        self.assertIn('hreflang="en"', content)
        self.assertIn('hreflang="uk"', content)
        self.assertIn('hreflang="x-default"', content)

    def test_page_language_urls_use_prefix_before_the_slug(self):
        configuration = SitemapSettings.get_solo()
        configuration.include_translations = True
        configuration.include_alternates = True
        configuration.save()

        response = self.client.get(
            reverse("sitemap-section", kwargs={"section": "pages"})
        )
        content = response.content.decode()

        self.assertIn("http://testserver/about/", content)
        self.assertIn("http://testserver/uk/about/", content)
        self.assertNotIn("http://testserver/about/uk/", content)
        self.assertIn(
            'hreflang="uk" href="http://testserver/uk/about/"',
            content,
        )

    def test_tags_are_not_a_sitemap_section(self):
        index_response = self.client.get(reverse("sitemap-index"))
        section_response = self.client.get(
            reverse("sitemap-section", kwargs={"section": "tags"})
        )

        self.assertNotContains(index_response, "/tag/")
        self.assertEqual(section_response.status_code, 404)

    def test_disabled_sitemap_returns_404_and_is_removed_from_robots(self):
        configuration = SitemapSettings.get_solo()
        configuration.enabled = False
        configuration.save()

        self.assertEqual(self.client.get(reverse("sitemap-index")).status_code, 404)
        robots = self.client.get("/robots.txt").content.decode()
        self.assertNotIn("Sitemap:", robots)

    def test_robots_contains_canonical_sitemap_url(self):
        response = self.client.get("/robots.txt")
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("User-agent: *", content)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", content)

    @override_settings(ALLOWED_HOSTS=["testserver", "preview.example.net"])
    def test_sitemap_uses_current_request_host_instead_of_saved_site_url(self):
        response = self.client.get(
            reverse("sitemap-section", kwargs={"section": "homepage"}),
            HTTP_HOST="preview.example.net:8443",
            secure=True,
        )
        robots = self.client.get(
            "/robots.txt",
            HTTP_HOST="preview.example.net:8443",
            secure=True,
        )

        self.assertContains(response, "https://preview.example.net:8443/")
        self.assertNotContains(response, "https://example.com/")
        self.assertContains(
            robots,
            "Sitemap: https://preview.example.net:8443/sitemap.xml",
        )
