import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.blog_manager.models import Article, Category
from apps.core_manager.demo_data import create_demo_data
from apps.core_manager.models import Page, SiteSettings


class DemoDataTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.user = get_user_model().objects.create_user(
            username="demo-author",
            email="demo@example.com",
        )

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_create_demo_data_builds_expected_structure_and_is_idempotent(self):
        first_result = create_demo_data(author=self.user)
        second_result = create_demo_data(author=self.user)

        self.assertEqual(first_result["articles_total"], 15)
        self.assertEqual(second_result["articles_created"], 0)
        self.assertEqual(Article.objects.count(), 15)
        self.assertEqual(Page.objects.filter(slug__in=["home", "about", "contact", "privacy"]).count(), 4)

        blog = Category.objects.get(slug="blog")
        news = Category.objects.get(slug="news")
        news_parent = Category.objects.get(slug="news-parent")
        news_2 = Category.objects.get(slug="news-2")
        self.assertIsNone(blog.parent)
        self.assertEqual(news.parent, blog)
        self.assertEqual(news_parent.parent, news)
        self.assertEqual(news_2.parent, blog)

        self.assertEqual(SiteSettings.get_solo().home_page, Page.objects.get(slug="home"))

        article = Article.objects.filter(category=news).first()
        self.assertNotIn("Demo", article.title)
        self.assertGreater(len(article.intro), 100)
        self.assertIn("<p>", article.body)
        self.assertGreater(len(article.body), 300)
        self.assertTrue(article.img.name.endswith(".avif"))
        self.assertTrue(article.img_crop.name.endswith("_crop.avif"))
        self.assertTrue(article.img_crop_mob.name.endswith("_crop_mob.avif"))
        self.assertTrue(os.path.exists(article.img.path))
        self.assertTrue(os.path.exists(article.img_crop.path))
        self.assertTrue(os.path.exists(article.img_crop_mob.path))

    def test_site_settings_admin_template_has_demo_data_button(self):
        template = get_template(
            "admin/core_manager/sitesettings/change_form.html"
        )
        create_url = reverse(
            "admin:core_manager_sitesettings_create_demo_data",
            args=[1],
        )

        self.assertIn(
            '{% trans "Create demo data" %}',
            template.template.source,
        )
        self.assertEqual(
            create_url,
            "/admin/core_manager/sitesettings/1/create-demo-data/",
        )
