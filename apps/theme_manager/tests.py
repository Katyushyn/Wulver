import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from apps.blog_manager.models import (
    Article,
    Category,
    ImageModule,
    LatestArticlesModule,
    TagModule,
)
from apps.core_manager.models import Page, SiteSettings
from apps.theme_manager.admin import ThemeTemplateAdmin, ThemeTemplateAdminForm
from apps.theme_manager.models import (
    TemplateComponent,
    Theme,
    ThemeTemplate,
    TemplateType,
)
from apps.theme_manager.template_load_analyzer import analyze_template_loads
from apps.theme_manager.asset_browser import save_uploaded_image
from apps.theme_manager.css_class_scanner import collect_template_css_classes


class TemplateCssClassScannerTest(SimpleTestCase):
    def test_collects_html_and_linked_css_classes_from_template_tree(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            templates = root / "templates" / "sample"
            styles = root / "static" / "sample"
            templates.mkdir(parents=True)
            styles.mkdir(parents=True)
            (templates / "article.html").write_text(
                "{% extends 'sample/base.html' %}"
                "{% include 'sample/card.html' %}"
                '<article class="article-body {{ dynamic_class }}"></article>',
                encoding="utf-8",
            )
            (templates / "base.html").write_text(
                "{% load static %}"
                "<link rel=\"stylesheet\" href=\"{% static 'sample/site.css' %}\">",
                encoding="utf-8",
            )
            (templates / "card.html").write_text(
                '<div class="card card-body"></div>',
                encoding="utf-8",
            )
            (styles / "site.css").write_text(
                ".lead, .col-md-4:hover { color: red; }"
                ".hero__title { background: url('../font.woff2'); }",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=root):
                classes = collect_template_css_classes(templates / "article.html")

        self.assertEqual(
            classes,
            ["article-body", "card", "card-body", "col-md-4", "hero__title", "lead"],
        )

class TemplateLoadAnalyzerTest(SimpleTestCase):
    def test_reports_missing_libraries(self):
        result = analyze_template_loads(
            "{% static 'img/logo.png' %}\n"
            "{% trans 'Hello' %}\n"
            "{% get_comment_count article as count %}"
        )

        missing = {item["library"] for item in result["missing"]}
        self.assertEqual(missing, {"static", "i18n", "comments"})

    def test_reports_unused_library(self):
        result = analyze_template_loads(
            "{% load static i18n comments %}\n"
            "{% static 'img/logo.png' %}\n"
            "{% trans 'Hello' %}"
        )

        self.assertEqual(result["unused"], ["comments"])
        self.assertEqual(result["missing"], [])

    def test_accepts_used_libraries(self):
        result = analyze_template_loads(
            "{% load static i18n comments %}\n"
            "{% static 'img/logo.png' %}\n"
            "{% trans 'Hello' %}\n"
            "{% get_comment_count article as count %}"
        )

        self.assertEqual(result["missing"], [])
        self.assertEqual(result["unused"], [])
        self.assertEqual(result["unknown"], [])

    def test_reports_unclosed_html_tags(self):
        result = analyze_template_loads(
            "<section>\n<div>\n<p>Content</p>\n</section>"
        )

        messages = [item["message"] for item in result["html_errors"]]
        self.assertIn("<div> is not closed before </section>.", messages)

    def test_reports_django_block_errors(self):
        result = analyze_template_loads(
            "{% if user %}\n{% for item in items %}\n{{ item }}\n{% endif %}"
        )

        messages = [item["message"] for item in result["django_block_errors"]]
        self.assertTrue(
            any("expected {% endfor %}" in message for message in messages)
        )
        self.assertTrue(
            any("expected {% endif %}" in message for message in messages)
        )

    def test_reports_invalid_static_and_media_urls(self):
        result = analyze_template_loads(
            '<img src="{% static \'/media/generated.avif\' %}">\n'
            '<img src="/static/images/logo.png">\n'
            '<img src="media/photo.jpg">\n'
            '<source srcset="static/one.jpg 1x, static/two.jpg 2x">\n'
            '<div style="background-image:url(media/background.jpg)"></div>'
        )

        messages = [item["message"] for item in result["url_issues"]]
        self.assertTrue(any("wrapped in {% static %}" in item for item in messages))
        self.assertTrue(any("raw static URL" in item for item in messages))
        self.assertTrue(any("relative media URL" in item for item in messages))
        self.assertTrue(any("srcset contains raw static URL" in item for item in messages))
        self.assertTrue(any("CSS url" in item for item in messages))

    def test_reports_duplicate_static_ids_but_ignores_dynamic_ids(self):
        result = analyze_template_loads(
            '<div id="hero"></div>\n'
            '<section id="hero"></section>\n'
            '<div id="item-{{ item.id }}"></div>\n'
            '<div id="item-{{ item.id }}"></div>'
        )

        self.assertEqual(len(result["duplicate_ids"]), 1)
        self.assertEqual(result["duplicate_ids"][0]["id"], "hero")
        self.assertEqual(result["duplicate_ids"][0]["lines"], [1, 2])

    def test_full_template_validation_passes(self):
        result = analyze_template_loads(
            "{% load static i18n %}\n"
            '<section id="hero">\n'
            '  <img src="{% static \'images/hero.jpg\' %}" alt="">\n'
            "  {% if title %}<h1>{% trans 'Welcome' %}</h1>{% endif %}\n"
            "</section>"
        )

        self.assertEqual(result["syntax_errors"], [])
        self.assertEqual(result["django_block_errors"], [])
        self.assertEqual(result["html_errors"], [])
        self.assertEqual(result["url_issues"], [])
        self.assertEqual(result["duplicate_ids"], [])

class AssetBrowserUploadTest(TestCase):
    def test_static_upload_defaults_to_current_theme_assets_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            static_root = Path(temporary_directory) / "static"
            media_root = Path(temporary_directory) / "media"

            with override_settings(
                STATICFILES_DIRS=[static_root],
                MEDIA_ROOT=media_root,
                STATIC_URL="/static/",
                MEDIA_URL="/media/",
            ):
                upload = SimpleUploadedFile(
                    "logo.png",
                    b"fake png bytes",
                    content_type="image/png",
                )

                asset, replaced = save_uploaded_image(
                    uploaded_file=upload,
                    asset_type="static",
                    target_path="logo.png",
                    default_static_prefix="themes/sample-theme/assets/img",
                )

                self.assertFalse(replaced)
                self.assertEqual(
                    asset["path"],
                    "themes/sample-theme/assets/img/logo.png",
                )
                self.assertTrue(
                    (
                        static_root
                        / "themes"
                        / "sample-theme"
                        / "assets"
                        / "img"
                        / "logo.png"
                    ).exists()
                )
                self.assertFalse((static_root / "logo.png").exists())

class TemplateAdminHelpersTest(TestCase):
    @patch("apps.theme_manager.admin.collect_template_css_classes", return_value=["card", "lead"])
    def test_saving_parent_article_replaces_detected_css_classes(self, collect_classes):
        theme = Theme.objects.create(name="CSS save", slug="css-save", is_active=True)
        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_ARTICLE,
            name="Article",
            slug="article",
            css_classes=["obsolete"],
        )
        request = RequestFactory().post("/admin/theme_manager/themetemplate/change/")
        request.user = User.objects.create_superuser(
            username="template-css-admin",
            email="template-css@example.com",
            password="test",
        )
        form = SimpleNamespace(cleaned_data={"template_html_code": '<article class="card"></article>'})

        with tempfile.TemporaryDirectory() as temporary_directory:
            with override_settings(BASE_DIR=Path(temporary_directory)):
                ThemeTemplateAdmin(ThemeTemplate, AdminSite()).save_model(
                    request,
                    template,
                    form,
                    change=True,
                )

        template.refresh_from_db()
        self.assertEqual(template.css_classes, ["card", "lead"])
        collect_classes.assert_called_once()

    def test_authentication_controls_component_is_seeded(self):
        component = TemplateComponent.objects.get(slug="authentication-controls")

        self.assertEqual(component.category, "Authentication")
        self.assertIn("{% authentication_button_url as authentication_url %}", component.code)
        self.assertIn('href="{{ authentication_url }}"', component.code)
        self.assertIn("fas fa-user", component.code)
        self.assertEqual(component.code.count("<a "), 1)

    def test_template_changelist_follows_template_type_hierarchy(self):
        theme = Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        templates = [
            ThemeTemplate.objects.create(
                theme=theme,
                template_type=template_type,
                name=name,
                slug=slug,
            )
            for template_type, name, slug in (
                (TemplateType.ERROR_TEMPLATE, "404", "404"),
                (TemplateType.PARENT_PAGE, "About", "about"),
                (TemplateType.INCLUDE_BLOCK, "Header", "header"),
                (TemplateType.BASE_TEMPLATE, "Base", "base"),
            )
        ]
        model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
        ordered = ThemeTemplate.objects.filter(pk__in=[obj.pk for obj in templates]).order_by(
            *model_admin.get_ordering(None)
        )

        self.assertEqual(
            list(ordered.values_list("template_type", flat=True)),
            [
                TemplateType.BASE_TEMPLATE,
                TemplateType.INCLUDE_BLOCK,
                TemplateType.PARENT_PAGE,
                TemplateType.ERROR_TEMPLATE,
            ],
        )
        self.assertEqual(model_admin.structured_name(templates[0]), "404")
        self.assertEqual(model_admin.structured_name(templates[3]), "Base")

    def test_obsolete_message_and_email_template_types_are_not_available(self):
        values = {value for value, _label in TemplateType.choices}

        self.assertNotIn("messages_template", values)
        self.assertNotIn("email_template", values)
        self.assertNotIn("system_page", values)

    def test_new_template_uses_active_theme_and_disables_theme_field(self):
        Theme.objects.create(name="Old", slug="old", is_active=False)
        active_theme = Theme.objects.create(
            name="Eterna",
            slug="eterna",
            is_active=True,
        )
        form = ThemeTemplateAdminForm(data={
            "template_type": TemplateType.INCLUDE_BLOCK,
            "name": "Header",
            "slug": "header",
            "is_active": "on",
        })

        self.assertTrue(form.fields["theme"].disabled)
        self.assertEqual(form.initial["theme"], active_theme)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().theme, active_theme)

    def test_existing_template_keeps_theme_field_disabled(self):
        theme = Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.INCLUDE_BLOCK,
            name="Header",
            slug="header",
        )

        form = ThemeTemplateAdminForm(instance=template)

        self.assertTrue(form.fields["theme"].disabled)

    def test_page_translation_fields_use_modeltranslation_tabs(self):
        form = ThemeTemplateAdminForm()

        self.assertIn(
            "mt-field-page_title-en",
            form.fields["page_title_en"].widget.attrs["class"],
        )
        self.assertIn(
            "mt-field-page_title-uk",
            form.fields["page_title_uk"].widget.attrs["class"],
        )
        self.assertIn(
            "mt-field-page_description-en",
            form.fields["page_description_en"].widget.attrs["class"],
        )
        self.assertIn(
            "modeltranslation/js/tabbed_translation_fields.js",
            ThemeTemplateAdmin(ThemeTemplate, AdminSite()).media._js,
        )
        media_js = ThemeTemplateAdmin(ThemeTemplate, AdminSite()).media._js
        self.assertIn("vendor/jquery-ui/jquery-ui.min.js", media_js)
        self.assertFalse(
            any(
                "ajax.googleapis.com/ajax/libs/jqueryui" in str(path)
                for path in media_js
            )
        )

    def test_article_extra_fields_schema_uses_article_fieldset(self):
        Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        form = ThemeTemplateAdminForm(data={
            "template_type": TemplateType.PARENT_ARTICLE,
            "name": "Article template",
            "slug": "article-template",
            "is_active": "on",
            "article_extra_fields_schema": json.dumps({
                "difficulty": {
                    "label": "Difficulty",
                    "type": "select",
                    "choices": ["Beginner", "Intermediate", "Advanced"],
                },
            }),
        })
        model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
        article_fieldsets = [
            fieldset
            for fieldset in model_admin.fieldsets
            if "theme-template-article-fields" in fieldset[1].get("classes", ())
        ]

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["article_extra_fields_schema"],
            {
                "difficulty": {
                    "label": "Difficulty",
                    "type": "select",
                    "choices": ["Beginner", "Intermediate", "Advanced"],
                },
            },
        )
        self.assertEqual(
            article_fieldsets[0][1]["fields"],
            ("article_extra_fields_schema",),
        )
        self.assertIn(
            "theme_manager/js/theme-template-page-fields.js",
            model_admin.media._js,
        )
        self.assertIn(
            "theme_manager/js/article-extra-fields-schema.js",
            form.media._js,
        )

    def test_article_extra_fields_schema_rejects_invalid_format(self):
        Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        form = ThemeTemplateAdminForm(data={
            "template_type": TemplateType.PARENT_ARTICLE,
            "name": "Article template",
            "slug": "article-template",
            "is_active": "on",
            "article_extra_fields_schema": json.dumps({
                "invalid-name": {
                    "label": "",
                    "type": "not-a-field",
                },
            }),
        })

        self.assertFalse(form.is_valid())
        self.assertIn("article_extra_fields_schema", form.errors)

    def test_article_extra_fields_schema_allows_checkbox_choices(self):
        Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        form = ThemeTemplateAdminForm(data={
            "template_type": TemplateType.PARENT_ARTICLE,
            "name": "Article template",
            "slug": "article-template",
            "is_active": "on",
            "article_extra_fields_schema": json.dumps({
                "technology": {
                    "label": "Technology",
                    "type": "checkbox",
                    "choices": ["bootstrap"],
                },
            }),
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_article_extra_fields_schema_renders_pretty_json(self):
        theme = Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_ARTICLE,
            name="Article template",
            slug="article-template",
            article_extra_fields_schema={
                "technology": {
                    "label": "Technology",
                    "type": "checkbox",
                    "choices": ["bootstrap"],
                },
            },
        )
        form = ThemeTemplateAdminForm(instance=template)

        self.assertIn(
            '{\n  &quot;technology&quot;: {\n    &quot;label&quot;: &quot;Technology&quot;',
            form["article_extra_fields_schema"].as_widget(),
        )

    def test_parent_page_form_creates_one_to_one_page(self):
        theme = Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        form = ThemeTemplateAdminForm(data={
            "theme": str(theme.pk),
            "template_type": TemplateType.PARENT_PAGE,
            "name": "About template",
            "slug": "about-template",
            "is_active": "on",
            "page_title_en": "About",
            "page_title_uk": "Про нас",
            "page_slug": "about",
            "page_description_en": "About the company",
            "page_description_uk": "Про компанію",
            "page_keywords": "company, team",
            "page_og_type": "website",
            "page_schema_graph": "{}",
            "page_is_published": "on",
        })

        self.assertTrue(form.is_valid(), form.errors)
        template = form.save()
        page = form.save_page()

        self.assertEqual(page.template, template)
        self.assertEqual(template.page, page)
        self.assertEqual(page.title_en, "About")
        self.assertEqual(page.title_uk, "Про нас")
        self.assertEqual(page.slug, "about")
        self.assertTrue(page.is_published)

    def test_parent_page_form_updates_existing_page(self):
        theme = Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_PAGE,
            name="About template",
            slug="about-template",
        )
        page = Page.objects.create(
            title="About",
            title_en="About",
            slug="about",
            description="Old description",
            description_en="Old description",
            template=template,
        )
        form = ThemeTemplateAdminForm(instance=template, data={
            "theme": str(theme.pk),
            "template_type": TemplateType.PARENT_PAGE,
            "name": template.name,
            "slug": template.slug,
            "is_active": "on",
            "page_title_en": "About us",
            "page_title_uk": "Про нас",
            "page_slug": "about",
            "page_description_en": "New description",
            "page_description_uk": "Новий опис",
            "page_schema_graph": "{}",
            "page_is_published": "on",
        })

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        saved_page = form.save_page()
        page.refresh_from_db()

        self.assertEqual(saved_page.pk, page.pk)
        self.assertEqual(page.title_en, "About us")
        self.assertEqual(page.description_uk, "Новий опис")
        self.assertEqual(Page.objects.filter(template=template).count(), 1)

    def test_non_parent_template_does_not_require_or_create_page(self):
        theme = Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        form = ThemeTemplateAdminForm(data={
            "theme": str(theme.pk),
            "template_type": TemplateType.INCLUDE_BLOCK,
            "name": "Header",
            "slug": "header",
            "is_active": "on",
        })

        self.assertTrue(form.is_valid(), form.errors)
        template = form.save()

        self.assertIsNone(form.save_page())
        self.assertFalse(Page.objects.filter(template=template).exists())

    def test_linked_parent_page_cannot_be_changed_to_another_template_type(self):
        theme = Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_PAGE,
            name="About template",
            slug="about-template",
        )
        Page.objects.create(
            title="About",
            title_en="About",
            slug="about",
            description="About the company",
            description_en="About the company",
            template=template,
        )
        form = ThemeTemplateAdminForm(instance=template, data={
            "theme": str(theme.pk),
            "template_type": TemplateType.INCLUDE_BLOCK,
            "name": template.name,
            "slug": template.slug,
            "is_active": "on",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("template_type", form.errors)

    def test_save_as_new_post_data_uses_unique_slug_with_source_id(self):
        theme = Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_PAGE,
            name="Home",
            slug="home",
        )
        ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_PAGE,
            name="Home copy",
            slug=f"home-{template.pk}",
        )
        admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
        request = RequestFactory().post(
            "/",
            data={
                "_saveasnew": "Save as new",
                "theme": str(theme.pk),
                "slug": "home",
            },
        )

        post_data = admin.get_save_as_new_post_data(
            request,
            object_id=str(template.pk),
        )

        self.assertEqual(post_data["slug"], f"home-{template.pk}-2")

    def test_lists_only_active_base_templates_for_extends(self):
        theme = Theme.objects.create(name="Eterna", slug="eterna", is_active=True)
        base = ThemeTemplate.objects.create(
            theme=theme,
            name="Base",
            slug="base",
            template_type=TemplateType.BASE_TEMPLATE,
            is_active=True,
        )
        ThemeTemplate.objects.create(
            theme=theme,
            name="Header",
            slug="header",
            template_type=TemplateType.INCLUDE_BLOCK,
            is_active=True,
        )
        ThemeTemplate.objects.create(
            theme=theme,
            name="Old base",
            slug="old-base",
            template_type=TemplateType.BASE_TEMPLATE,
            is_active=False,
        )

        templates = ThemeTemplateAdmin.get_base_templates_for_theme(theme)

        self.assertEqual(templates, [
            {
                "name": base.name,
                "slug": base.slug,
                "extends": "{% extends 'eterna/base.html' %}",
            }
        ])

class TextGenerationTest(TestCase):
    def test_generates_plain_text_for_selected_content(self):
        ai_response = SimpleNamespace(
            output_text="```text\nНовий текст для головної сторінки.\n```"
        )

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                openai_class.return_value.responses.create.return_value = ai_response
                model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
                response = model_admin.generate_selected_text_response(
                    selected_text="Старий текст",
                    text_prompt="Українською, дружній стиль, до 100 символів",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)["code"],
            "Новий текст для головної сторінки.",
        )
        prompt = openai_class.return_value.responses.create.call_args.kwargs["input"]
        self.assertIn("до 100 символів", prompt)
        self.assertIn("Старий текст", prompt)

    def test_requires_text_generation_instruction(self):
        model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())

        response = model_admin.generate_selected_text_response(
            selected_text="Старий текст",
            text_prompt="",
        )

        self.assertEqual(response.status_code, 400)


class HtmlGenerationTest(TestCase):
    def test_generates_html_for_selected_code(self):
        ai_response = SimpleNamespace(
            output_text=(
                "```html\n"
                '<div class="row"><div class="col-md-6">{{ title }}</div>'
                '<div class="col-md-6">Text</div></div>\n'
                "```"
            )
        )

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                openai_class.return_value.responses.create.return_value = ai_response
                model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
                response = model_admin.generate_selected_html_response(
                    selected_code='<div class="row">{{ title }}</div>',
                    html_prompt="make two Bootstrap columns and preserve classes",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)["code"],
            '<div class="row"><div class="col-md-6">{{ title }}</div>'
            '<div class="col-md-6">Text</div></div>',
        )
        prompt = openai_class.return_value.responses.create.call_args.kwargs["input"]
        self.assertIn("make two Bootstrap columns", prompt)
        self.assertIn("Preserve existing CSS classes", prompt)
        self.assertIn("Preserve Django template syntax", prompt)

    def test_requires_html_generation_instruction(self):
        model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())

        response = model_admin.generate_selected_html_response(
            selected_code='<div class="row">{{ title }}</div>',
            html_prompt="",
        )

        self.assertEqual(response.status_code, 400)


class ComponentConversionTest(TestCase):
    def test_article_navigation_components_are_separate(self):
        previous = TemplateComponent.objects.get(slug="previous-article")
        next_component = TemplateComponent.objects.get(slug="next-article")

        self.assertIn("{% if prev_article %}", previous.code)
        self.assertNotIn("next_article", previous.code)
        self.assertIn("{% if next_article %}", next_component.code)
        self.assertNotIn("prev_article", next_component.code)

    def test_lists_active_template_components_for_editor(self):
        TemplateComponent.objects.create(
            name="Hero block",
            slug="hero-block",
            category="Content",
            icon="web_asset",
            description="Reusable hero",
            code="<section>Hero</section>",
            is_active=True,
            sort_order=1,
        )
        TemplateComponent.objects.create(
            name="Inactive block",
            slug="inactive-block",
            category="Content",
            code="<section>Hidden</section>",
            is_active=False,
        )
        request = RequestFactory().get("/admin/theme_manager/themetemplate/change-tools/components/")
        request.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test",
        )

        model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
        response = model_admin.template_editor_components_view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        slugs = {component["slug"] for component in data["components"]}
        self.assertIn("hero-block", slugs)
        self.assertNotIn("inactive-block", slugs)

    def test_latest_articles_component_exposes_related_modules_for_second_choice(self):
        component = TemplateComponent.objects.get(slug="latest-blog-articles")
        module = LatestArticlesModule.objects.create(
            name="Latest AI",
            slug="latest-ai",
            articles_count=4,
        )
        request = RequestFactory().get(
            "/admin/theme_manager/themetemplate/change-tools/components/"
        )
        request.user = User.objects.create_superuser(
            username="module-admin",
            email="module-admin@example.com",
            password="test",
        )

        response = ThemeTemplateAdmin(
            ThemeTemplate,
            AdminSite(),
        ).template_editor_components_view(request)
        components = json.loads(response.content)["components"]
        latest_component = next(
            item for item in components
            if item["slug"] == "latest-blog-articles"
        )
        module_option = latest_component["modules"][0]

        self.assertEqual(latest_component["name"], "Latest blog articles")
        self.assertEqual(module_option["name"], "Latest AI")
        self.assertEqual(module_option["slug"], "latest-ai")
        self.assertIn(
            '{% latest_articles_module "latest-ai" as latest_blog_articles %}',
            module_option["code"],
        )

    def test_latest_articles_component_has_empty_module_list_when_none_exist(self):
        request = RequestFactory().get(
            "/admin/theme_manager/themetemplate/change-tools/components/"
        )
        request.user = User.objects.create_superuser(
            username="empty-module-admin",
            email="empty-module-admin@example.com",
            password="test",
        )

        response = ThemeTemplateAdmin(
            ThemeTemplate,
            AdminSite(),
        ).template_editor_components_view(request)
        components = json.loads(response.content)["components"]
        latest_component = next(
            item for item in components
            if item["slug"] == "latest-blog-articles"
        )

        self.assertEqual(latest_component["modules"], [])

    def test_tags_component_exposes_tag_modules_for_second_choice(self):
        component = TemplateComponent.objects.get(slug="tags-cloud")
        component.tag_modules.clear()
        TagModule.objects.all().delete()
        module = TagModule.objects.create(
            name="Article badges",
            slug="article-badges",
            source=TagModule.Source.CURRENT_ARTICLE,
            classes="badge-info, badge-success",
            class_mode=TagModule.ClassMode.SEQUENTIAL,
        )
        request = RequestFactory().get(
            "/admin/theme_manager/themetemplate/change-tools/components/"
        )
        request.user = User.objects.create_superuser(
            username="tag-module-admin",
            email="tag-module-admin@example.com",
            password="test",
        )

        response = ThemeTemplateAdmin(
            ThemeTemplate,
            AdminSite(),
        ).template_editor_components_view(request)
        components = json.loads(response.content)["components"]
        tags_component = next(
            item for item in components
            if item["slug"] == "tags-cloud"
        )
        module_option = tags_component["modules"][0]

        self.assertEqual(tags_component["name"], "Tags")
        self.assertEqual(module_option["name"], "Article badges")
        self.assertEqual(module_option["slug"], "article-badges")
        self.assertIn(
            '{% tags_module "article-badges" as module_tags %}',
            module_option["code"],
        )
        self.assertIn("{{ item.css_class }}", module_option["code"])

    def test_tags_component_has_empty_module_list_when_none_exist(self):
        component = TemplateComponent.objects.get(slug="tags-cloud")
        component.tag_modules.clear()
        TagModule.objects.all().delete()
        request = RequestFactory().get(
            "/admin/theme_manager/themetemplate/change-tools/components/"
        )
        request.user = User.objects.create_superuser(
            username="empty-tag-module-admin",
            email="empty-tag-module-admin@example.com",
            password="test",
        )

        response = ThemeTemplateAdmin(
            ThemeTemplate,
            AdminSite(),
        ).template_editor_components_view(request)
        components = json.loads(response.content)["components"]
        tags_component = next(
            item for item in components
            if item["slug"] == "tags-cloud"
        )

        self.assertEqual(tags_component["modules"], [])

    def test_images_component_exposes_image_modules_for_second_choice(self):
        module = ImageModule.objects.create(
            name="Homepage gallery",
            slug="test-homepage-gallery",
        )
        request = RequestFactory().get(
            "/admin/theme_manager/themetemplate/change-tools/components/"
        )
        request.user = User.objects.create_superuser(
            username="image-module-admin",
            email="image-module-admin@example.com",
            password="test",
        )

        response = ThemeTemplateAdmin(
            ThemeTemplate,
            AdminSite(),
        ).template_editor_components_view(request)
        components = json.loads(response.content)["components"]
        images_component = next(
            item for item in components
            if item["slug"] == "images"
        )
        module_option = next(
            item for item in images_component["modules"]
            if item["slug"] == module.slug
        )

        self.assertEqual(images_component["name"], "Images")
        self.assertIn(
            '{% image_module "test-homepage-gallery" as module_images %}',
            module_option["code"],
        )
        self.assertIn("{{ image.crop_mob_url }}", module_option["code"])
        self.assertIn("{{ image.crop_url }}", module_option["code"])
        self.assertIn(
            "{% firstof image.crop_url image.url %}",
            module_option["code"],
        )

    def test_lists_paginated_cms_link_options_for_editor(self):
        category = Category.objects.create(
            title="Business",
            slug="business",
            description="Business category",
        )
        article = Article.objects.create(
            title="Business article",
            slug="business-article",
            description="Article description",
            intro="Intro",
            body="Body",
            category=category,
            is_published=True,
        )
        Page.objects.create(
            title="About",
            slug="about",
            description="About page",
            is_published=True,
        )
        request = RequestFactory().get(
            "/admin/theme_manager/themetemplate/change-tools/cms-link-options/",
            {"type": "article", "q": "Business", "page": 1},
        )
        request.user = User.objects.create_superuser(
            username="cms-link-admin",
            email="cms-link@example.com",
            password="test",
        )

        response = ThemeTemplateAdmin(
            ThemeTemplate,
            AdminSite(),
        ).template_editor_cms_link_options_view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["items"][0]["id"], article.pk)
        self.assertEqual(
            data["items"][0]["url_tag"],
            "{% url 'blog:post' category_slug='business' "
            "post_slug='business-article' %}",
        )
        self.assertEqual(
            data["items"][0]["url"],
            "/business/business-article/",
        )
        self.assertFalse(data["has_more"])

    def test_cms_link_option_uses_home_url_for_homepage_page(self):
        page = Page.objects.create(
            title="Homepage",
            slug="homepage",
            description="Homepage",
            is_published=True,
        )
        site_settings = SiteSettings.get_solo()
        site_settings.home_page = page
        site_settings.save(update_fields=["home_page"])
        request = RequestFactory().get(
            "/admin/theme_manager/themetemplate/change-tools/cms-link-options/",
            {"type": "page", "q": "Homepage"},
        )
        request.user = User.objects.create_superuser(
            username="homepage-link-admin",
            email="homepage-link@example.com",
            password="test",
        )

        response = ThemeTemplateAdmin(
            ThemeTemplate,
            AdminSite(),
        ).template_editor_cms_link_options_view(request)

        data = json.loads(response.content)
        self.assertEqual(data["items"][0]["url_tag"], "{% url 'core_manager:home' %}")

    def test_lists_blog_category_tree_for_editor(self):
        parent = Category.objects.create(
            title="Templates",
            slug="templates",
            description="Templates",
            sort_order=1,
        )
        child = Category.objects.create(
            title="Django",
            slug="django",
            description="Django",
            parent=parent,
            sort_order=1,
        )
        request = RequestFactory().get(
            "/admin/theme_manager/themetemplate/change-tools/blog-category-tree/"
        )
        request.user = User.objects.create_superuser(
            username="category-tree-admin",
            email="category-tree@example.com",
            password="test",
        )

        response = ThemeTemplateAdmin(
            ThemeTemplate,
            AdminSite(),
        ).template_editor_blog_category_tree_view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(
            [(item["id"], item["depth"], item["child_count"]) for item in data["items"]],
            [(parent.pk, 0, 1), (child.pk, 1, 0)],
        )

    def test_converts_blog_category_children_component_with_selected_category(self):
        ai_response = SimpleNamespace(
            output_text=(
                "{% load blog_categories %}\n"
                "{% get_blog_category_children 12 as child_categories %}\n"
                "<ul>{% for child_category in child_categories %}"
                "<li><a href=\"{% url 'blog:category' category_slug=child_category.slug %}\">"
                "{{ child_category.title }}</a></li>{% endfor %}</ul>"
            )
        )

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                openai_class.return_value.responses.create.return_value = ai_response
                response = ThemeTemplateAdmin(
                    ThemeTemplate,
                    AdminSite(),
                ).convert_selected_component_response(
                    selected_code='<ul class="nav"><li><a><i class="bi"></i>Static</a></li></ul>',
                    component_type="blog_category_children",
                    category_id="12",
                    category_title="Templates",
                    category_slug="templates",
                    category_instruction="Make the category list two columns like the selected example.",
                )

        self.assertEqual(response.status_code, 200)
        prompt = openai_class.return_value.responses.create.call_args.kwargs["input"]
        self.assertIn("get_blog_category_children", prompt)
        self.assertIn("id: 12", prompt)
        self.assertIn("title: Templates", prompt)
        self.assertIn(
            "Make the category list two columns like the selected example.",
            prompt,
        )

    def test_converts_latest_blog_articles_component(self):
        ai_response = SimpleNamespace(
            output_text=(
                "{% if latest_blog_articles %}"
                "{% for article in latest_blog_articles %}"
                "<article>{{ article.title }}</article>"
                "{% endfor %}{% endif %}"
            )
        )

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                openai_class.return_value.responses.create.return_value = ai_response
                response = ThemeTemplateAdmin(
                    ThemeTemplate,
                    AdminSite(),
                ).convert_selected_component_response(
                    selected_code='<div class="card"><h2>Static title</h2></div>',
                    component_type="latest_blog_articles",
                )

        self.assertEqual(response.status_code, 200)
        prompt = openai_class.return_value.responses.create.call_args.kwargs["input"]
        self.assertIn("latest_blog_articles", prompt)
        self.assertIn("Never use articles for this module", prompt)
        self.assertIn("article.category.slug plus article.slug", prompt)

    def test_uses_template_component_ai_prompt_when_available(self):
        TemplateComponent.objects.update_or_create(
            slug="comments",
            defaults={
                "name": "Django comments",
                "category": "Content",
                "icon": "comment",
                "description": "",
                "code": "{% load comments %}",
                "ai_conversion_prompt": "Use the editable comments prompt from the database.",
                "is_active": True,
            },
        )
        ai_response = SimpleNamespace(output_text="{% load comments %}")

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                openai_class.return_value.responses.create.return_value = ai_response
                model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
                response = model_admin.convert_selected_component_response(
                    selected_code='<section class="comments">Static comments</section>',
                    component_type="comments",
                )

        self.assertEqual(response.status_code, 200)
        prompt = openai_class.return_value.responses.create.call_args.kwargs["input"]
        self.assertIn("Use the editable comments prompt from the database.", prompt)

    def test_converts_selected_comments_component(self):
        ai_response = SimpleNamespace(
            output_text=(
                "```html\n"
                "{% load comments %}\n"
                "{% if page %}{% render_comment_form for page %}{% endif %}\n"
                "```"
            )
        )

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                openai_class.return_value.responses.create.return_value = ai_response
                model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
                response = model_admin.convert_selected_component_response(
                    selected_code='<section class="comments">Static comments</section>',
                    component_type="comments",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)["code"],
            "{% load comments %}\n"
            "{% if page %}{% render_comment_form for page %}{% endif %}",
        )
        prompt = openai_class.return_value.responses.create.call_args.kwargs["input"]
        self.assertIn("Do not use {% firstof ... as comment_object %}", prompt)
        self.assertIn("Use explicit branches for object, article, and page.", prompt)
        self.assertIn('<section class="comments">Static comments</section>', prompt)

    def test_rejects_unknown_component_conversion(self):
        model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())

        response = model_admin.convert_selected_component_response(
            selected_code="<nav></nav>",
            component_type="unknown",
        )

        self.assertEqual(response.status_code, 400)
