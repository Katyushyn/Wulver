from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.test import TestCase
from django.utils import translation
from modeltranslation.translator import translator

from apps.core_manager.models import Page, SiteSettings, URLLink

from .models import Article, ArticleImage, Category, Tag


class MultilingualContentTests(TestCase):
    translated_fields = {
        Category: {"title", "description", "intro", "keywords"},
        Article: {"title", "description", "intro", "body", "keywords"},
        Tag: {"title"},
        ArticleImage: {"alt_text"},
        Page: {"title", "description", "keywords"},
        SiteSettings: {
            "site_name",
            "title",
            "description",
            "default_image_alt",
            "author_name",
            "og_site_name",
            "organization_name",
            "person_name",
            "person_job_title",
            "maintenance_message",
        },
        URLLink: {"title"},
    }

    def test_requested_models_and_fields_are_registered(self):
        for model, expected_fields in self.translated_fields.items():
            options = translator.get_options_for_model(model)
            self.assertSetEqual(set(options.fields), expected_fields)

            for field_name in expected_fields:
                self.assertIsNotNone(model._meta.get_field(f"{field_name}_en"))
                self.assertIsNotNone(model._meta.get_field(f"{field_name}_uk"))

    def test_active_language_selects_translation_with_english_fallback(self):
        page = Page(
            slug="multilingual",
            title_en="English title",
            title_uk="Український заголовок",
            description_en="English description",
            description_uk="Український опис",
        )

        with translation.override("uk"):
            self.assertEqual(page.title, "Український заголовок")
            self.assertEqual(page.description, "Український опис")

        page.title_uk = ""
        with translation.override("uk"):
            self.assertEqual(page.title, "English title")

    def test_category_requires_default_language_content_and_pagination_limit(self):
        request = RequestFactory().get("/")
        request.user = User(is_staff=True, is_superuser=True)
        request.resolver_match = SimpleNamespace(kwargs={})
        category_admin = admin.site._registry[Category]
        form = category_admin.get_form(request)()

        required_fields = {
            name
            for name, field in form.fields.items()
            if field.required
        }

        self.assertSetEqual(
            required_fields,
            {"title_en", "description_en", "articles_per_page"},
        )
