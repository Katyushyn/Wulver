from types import SimpleNamespace
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from django.utils.translation import override
from PIL import Image

from apps.core_manager.models import Page, SiteSettings
from apps.core_manager.seo import build_schema_graph
from apps.theme_manager.admin import ThemeTemplateAdmin
from apps.theme_manager.models import TemplateType, Theme, ThemeTemplate

from .context_processors import blog_context, get_latest_blog_articles, get_tag_cloud
from .admin import ArticleAdmin, ArticleAdminForm
from .article_preview import render_article_body_preview
from .models import (
    Article,
    BlogSettings,
    Category,
    LatestArticlesModule,
    Tag,
    TagModule,
)
from .views import (
    BlogCategoryView,
    _article_navigation,
    get_article_template,
    get_category_template,
)


class BlogSettingsTemplateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        theme = Theme.objects.create(name="Test", slug="test", is_active=True)
        cls.category_template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_BLOG,
            name="Category",
            slug="category",
        )
        cls.paginated_template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_BLOG,
            name="Category paginated",
            slug="category-paginated",
        )
        cls.article_template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_ARTICLE,
            name="Article",
            slug="article",
        )
        cls.page_template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_PAGE,
            name="Page",
            slug="page",
        )
        settings = BlogSettings.get_solo()
        settings.default_category_template = cls.category_template
        settings.default_paginated_category_template = cls.paginated_template
        settings.default_article_template = cls.article_template
        settings.save()

    def test_category_uses_first_and_paginated_defaults(self):
        category = SimpleNamespace(
            theme_template=None,
            paginated_theme_template=None,
        )

        self.assertEqual(get_category_template(category), self.category_template)
        self.assertEqual(
            get_category_template(category, page_number="2"),
            self.paginated_template,
        )

    def test_article_uses_default_after_article_and_category(self):
        article = SimpleNamespace(
            theme_template=None,
            category=SimpleNamespace(article_theme_template=None),
        )

        self.assertEqual(get_article_template(article), self.article_template)

    def test_blog_settings_autocomplete_filters_template_types(self):
        model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
        category_request = RequestFactory().get(
            "/admin/autocomplete/",
            {
                "app_label": "blog_manager",
                "model_name": "blogsettings",
                "field_name": "default_category_template",
            },
        )
        article_request = RequestFactory().get(
            "/admin/autocomplete/",
            {
                "app_label": "blog_manager",
                "model_name": "blogsettings",
                "field_name": "default_article_template",
            },
        )

        category_queryset, _ = model_admin.get_search_results(
            category_request,
            ThemeTemplate.objects.all(),
            "",
        )
        article_queryset, _ = model_admin.get_search_results(
            article_request,
            ThemeTemplate.objects.all(),
            "",
        )

        self.assertSetEqual(
            set(category_queryset.values_list("template_type", flat=True)),
            {TemplateType.PARENT_BLOG},
        )
        self.assertSetEqual(
            set(article_queryset.values_list("template_type", flat=True)),
            {TemplateType.PARENT_ARTICLE},
        )


class CategoryArticlePaginationTests(TestCase):
    def test_category_defaults_to_five_articles_per_page(self):
        category = Category.objects.create(
            title="News",
            slug="news-pagination-default",
            description="News category",
        )

        self.assertEqual(category.articles_per_page, 5)

    def test_category_view_uses_its_articles_per_page_setting(self):
        view = BlogCategoryView()
        view.category_obj = SimpleNamespace(articles_per_page=8)

        self.assertEqual(view.get_paginate_by(queryset=None), 8)


class ArticleNavigationTests(TestCase):
    def test_navigation_uses_current_category_and_descendants_only(self):
        now = timezone.now()
        parent = Category.objects.create(
            title="Business",
            slug="navigation-business",
            description="Business",
        )
        child = Category.objects.create(
            title="Corporate templates",
            slug="navigation-corporate",
            description="Corporate templates",
            parent=parent,
        )
        parallel = Category.objects.create(
            title="Portfolio templates",
            slug="navigation-portfolio",
            description="Portfolio templates",
        )
        current = Article.objects.create(
            title="Current",
            slug="navigation-current",
            description="Current",
            intro="Current",
            body="Current",
            category=parent,
            publish=now - timezone.timedelta(days=2),
        )
        previous = Article.objects.create(
            title="Previous child",
            slug="navigation-previous-child",
            description="Previous child",
            intro="Previous child",
            body="Previous child",
            category=child,
            publish=now - timezone.timedelta(days=3),
        )
        next_article = Article.objects.create(
            title="Next parent",
            slug="navigation-next-parent",
            description="Next parent",
            intro="Next parent",
            body="Next parent",
            category=parent,
            publish=now - timezone.timedelta(days=1),
        )
        Article.objects.create(
            title="Closer parallel article",
            slug="navigation-closer-parallel",
            description="Parallel",
            intro="Parallel",
            body="Parallel",
            category=parallel,
            publish=now - timezone.timedelta(hours=36),
        )

        navigation = _article_navigation(current)

        self.assertEqual(navigation["prev_article"], previous)
        self.assertEqual(navigation["next_article"], next_article)


class ArticleImageProcessingTests(TestCase):
    def test_removes_uploaded_source_after_creating_avif_variants(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                category = Category.objects.create(
                    title="Images",
                    slug="article-image-processing",
                    description="Images",
                )
                upload = tempfile.SpooledTemporaryFile()
                Image.new("RGB", (1600, 1000), "blue").save(upload, format="PNG")
                upload.seek(0)

                article = Article.objects.create(
                    title="Processed image",
                    slug="processed-article-image",
                    description="Processed image",
                    intro="Processed image",
                    body="Processed image",
                    category=category,
                    img=SimpleUploadedFile(
                        "source.png",
                        upload.read(),
                        content_type="image/png",
                    ),
                )
                article.refresh_from_db()

                media_path = Path(media_root)
                self.assertEqual(list(media_path.rglob("*.png")), [])
                self.assertTrue(article.img.name.endswith(".avif"))
                self.assertTrue(article.img_crop.name.endswith("_crop.avif"))
                self.assertTrue(article.img_crop_mob.name.endswith("_crop_mob.avif"))

                with Image.open(article.img_crop.path) as desktop:
                    self.assertEqual(desktop.size, (600, 400))
                with Image.open(article.img_crop_mob.path) as mobile:
                    self.assertEqual(mobile.size, (380, 253))


class LatestArticlesModuleTests(TestCase):
    def test_template_tag_filters_categories_includes_descendants_and_limits_results(self):
        now = timezone.now()
        parent = Category.objects.create(
            title="Development",
            slug="module-development",
            description="Development",
        )
        child = Category.objects.create(
            title="Django",
            slug="module-django",
            description="Django",
            parent=parent,
        )
        other = Category.objects.create(
            title="Travel",
            slug="module-travel",
            description="Travel",
        )
        older = Article.objects.create(
            title="Older",
            slug="module-older",
            description="Older",
            intro="Older",
            body="Older",
            category=parent,
            publish=now - timezone.timedelta(days=2),
        )
        newer = Article.objects.create(
            title="Newer child",
            slug="module-newer-child",
            description="Newer",
            intro="Newer",
            body="Newer",
            category=child,
            publish=now - timezone.timedelta(days=1),
        )
        Article.objects.create(
            title="Other",
            slug="module-other",
            description="Other",
            intro="Other",
            body="Other",
            category=other,
            publish=now,
        )
        module = LatestArticlesModule.objects.create(
            name="Development latest",
            slug="development-latest",
            articles_count=2,
        )
        module.categories.add(parent)

        rendered = Template(
            "{% load blog_modules %}"
            "{% latest_articles_module 'development-latest' as module_articles %}"
            "{% for article in module_articles %}{{ article.pk }},{% endfor %}"
        ).render(Context())

        self.assertEqual(rendered, f"{newer.pk},{older.pk},")

    def test_inactive_or_unknown_module_returns_no_articles(self):
        LatestArticlesModule.objects.create(
            name="Inactive",
            slug="inactive-latest",
            is_active=False,
        )

        rendered = Template(
            "{% load blog_modules %}"
            "{% latest_articles_module 'inactive-latest' as module_articles %}"
            "{{ module_articles|length }}"
        ).render(Context())

        self.assertEqual(rendered, "0")


class TagModuleTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            title="Development",
            slug="tag-module-development",
            description="Development",
        )
        self.article = Article.objects.create(
            title="Django module",
            slug="tag-module-article",
            description="Django module",
            intro="Intro",
            body="Body",
            category=self.category,
        )
        self.alpha = Tag.objects.create(title="Alpha", slug="tag-module-alpha")
        self.beta = Tag.objects.create(title="Beta", slug="tag-module-beta")
        self.gamma = Tag.objects.create(title="Gamma", slug="tag-module-gamma")
        self.article.tags.add(self.alpha, self.beta, self.gamma)

    def render_module(self, module):
        return Template(
            "{% load blog_modules %}"
            f"{{% tags_module '{module.slug}' as module_tags %}}"
            "{% for item in module_tags %}{{ item.title }}={{ item.css_class }};{% endfor %}"
        ).render(Context({"article": self.article, "category": self.category}))

    def test_assigns_one_class_per_tag_in_order(self):
        module = TagModule.objects.create(
            name="Sequential",
            slug="tag-module-sequential",
            tags_count=3,
            classes="first, second",
            class_mode=TagModule.ClassMode.SEQUENTIAL,
        )

        self.assertEqual(
            self.render_module(module),
            "Alpha=first;Beta=second;Gamma=first;",
        )

    def test_assigns_all_classes_to_every_tag(self):
        module = TagModule.objects.create(
            name="All",
            slug="tag-module-all",
            tags_count=1,
            classes="badge, badge-info, badge-lg",
            class_mode=TagModule.ClassMode.ALL,
        )

        self.assertEqual(
            self.render_module(module),
            "Alpha=badge badge-info badge-lg;",
        )

    def test_assigns_one_random_class_to_each_tag(self):
        module = TagModule.objects.create(
            name="Random",
            slug="tag-module-random",
            tags_count=3,
            classes="first, second, third",
            class_mode=TagModule.ClassMode.RANDOM,
        )

        rendered = self.render_module(module)
        assigned = [
            item.split("=")[1]
            for item in rendered.strip(";").split(";")
        ]

        self.assertEqual(len(assigned), 3)
        self.assertTrue(all(css_class in {"first", "second", "third"} for css_class in assigned))

    def test_empty_classes_adds_no_module_class(self):
        module = TagModule.objects.create(
            name="No classes",
            slug="tag-module-no-classes",
            tags_count=1,
            classes="",
        )

        self.assertEqual(self.render_module(module), "Alpha=;")

    def test_global_cloud_orders_by_popularity_and_applies_limit(self):
        second_article = Article.objects.create(
            title="Second",
            slug="tag-module-second-article",
            description="Second",
            intro="Intro",
            body="Body",
            category=self.category,
        )
        second_article.tags.add(self.beta)
        module = TagModule.objects.create(
            name="Popular",
            slug="tag-module-popular",
            source=TagModule.Source.GLOBAL_CLOUD,
            ordering=TagModule.Ordering.POPULARITY,
            tags_count=1,
        )

        self.assertEqual(self.render_module(module), "Beta=;")


class ArticleExtraFieldsAdminTests(TestCase):
    def setUp(self):
        self.theme = Theme.objects.create(name="Test", slug="test", is_active=True)
        self.article_template = ThemeTemplate.objects.create(
            theme=self.theme,
            template_type=TemplateType.PARENT_ARTICLE,
            name="Article",
            slug="article",
            article_extra_fields_schema={
                "difficulty": {
                    "label": "Difficulty",
                    "type": "select",
                    "choices": ["Beginner", "Advanced"],
                },
                "is_featured": {
                    "label": "Featured",
                    "type": "checkbox",
                },
                "technology": {
                    "label": "Technology",
                    "type": "checkbox",
                    "choices": ["bootstrap"],
                },
                "score": {
                    "label": "Score",
                    "type": "number",
                },
                "broken": {
                    "label": "Broken",
                    "type": "file",
                },
            },
        )
        self.category = Category.objects.create(
            title="News",
            slug="news",
            description="News category",
            intro="News intro",
            article_theme_template=self.article_template,
        )

    def test_article_form_cleans_extra_fields_from_category_template_schema(self):
        form = ArticleAdminForm(data={
            "title": "Article",
            "slug": "article-extra-fields",
            "description": "Description",
            "keywords": "",
            "category": str(self.category.pk),
            "theme_template": "",
            "status": "standard",
            "is_published": "on",
            "publish": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "preview_image": "",
            "og_type": "",
            "schema_graph": "{}",
            "canonical_allowed_params": "",
            "noindex": "",
            "intro": "Intro",
            "body": "Body",
            "article_extra_fields": json.dumps({
                "difficulty": "Advanced",
                "is_featured": True,
                "technology": "bootstrap",
                "score": "10",
                "unknown": "drop me",
            }),
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["article_extra_fields"],
            {
                "difficulty": "Advanced",
                "is_featured": True,
                "technology": "bootstrap",
                "score": 10,
            },
        )

    def test_article_extra_fields_schema_endpoint_returns_valid_fields_only(self):
        request = RequestFactory().get(
            "/admin/blog_manager/article/extra-fields-schema/",
            {"category_id": self.category.pk},
        )
        request.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        response = ArticleAdmin(Article, AdminSite()).extra_fields_schema_view(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [field["name"] for field in payload["fields"]],
            ["difficulty", "is_featured", "technology", "score"],
        )


class ArticleBodyEditorAdminTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/blog_manager/article/add/")
        self.request.user = User(
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        self.model_admin = ArticleAdmin(Article, AdminSite())

    def test_localized_body_fields_use_the_html_code_editor(self):
        form = self.model_admin.get_form(self.request)()

        self.assertEqual(
            form.fields["body_en"].widget.__class__.__name__,
            "UnfoldAdminTextareaWidget",
        )
        self.assertEqual(
            form.fields["body_uk"].widget.__class__.__name__,
            "UnfoldAdminTextareaWidget",
        )
        self.assertIn(
            "codemirror-article-body",
            form.fields["body_en"].widget.attrs["class"],
        )
        self.assertIn(
            "codemirror-article-body",
            form.fields["body_uk"].widget.attrs["class"],
        )
        self.assertIn("mt-field-body-en", form.fields["body_en"].widget.attrs["class"])
        self.assertIn("mt-field-body-uk", form.fields["body_uk"].widget.attrs["class"])
        self.assertIn(
            "/admin/blog_manager/article/ai-edit-text/",
            form.fields["body_en"].widget.attrs["data-ai-edit-url"],
        )
        self.assertIn(
            "/admin/blog_manager/article/body-preview/",
            form.fields["body_en"].widget.attrs["data-preview-url"],
        )
        self.assertIn(
            "/admin/blog_manager/article/cms-link-options/",
            form.fields["body_en"].widget.attrs["data-cms-link-options-url"],
        )
        self.assertIn(
            "/admin/blog_manager/article/css-classes/",
            form.fields["body_en"].widget.attrs["data-css-classes-url"],
        )
        self.assertEqual(form.fields["body_en"].widget.attrs["data-language"], "en")
        self.assertEqual(form.fields["body_uk"].widget.attrs["data-language"], "uk")

    @patch(
        "apps.blog_manager.admin.render_article_body_preview",
        return_value="<!doctype html><html><body>Preview</body></html>",
    )
    def test_body_preview_uses_selected_category_template_and_language(self, render_preview):
        category = Category.objects.create(
            title="Preview category",
            slug="preview-category",
            description="Preview category",
        )
        article = Article.objects.create(
            title="Saved title",
            slug="preview-article",
            description="Description",
            intro="Intro",
            body="Saved body",
            category=category,
        )
        request = RequestFactory().post(
            "/admin/blog_manager/article/body-preview/",
            {
                "article_id": article.pk,
                "category_id": category.pk,
                "language": "uk",
                "title": "Нова назва",
                "body_html": '<p class="lead">Новий текст</p>',
            },
        )
        request.user = User.objects.create_superuser(
            username="preview-admin",
            email="preview@example.com",
            password="test",
        )

        response = self.model_admin.body_preview_view(request)

        self.assertEqual(response.status_code, 200)
        preview_article, preview_body = render_preview.call_args.args[1:]
        self.assertEqual(preview_article.category_id, category.pk)
        self.assertEqual(preview_article.title_uk, "Нова назва")
        self.assertEqual(preview_body, '<p class="lead">Новий текст</p>')

    def test_body_preview_requires_a_category(self):
        request = RequestFactory().post(
            "/admin/blog_manager/article/body-preview/",
            {"body_html": "<p>Preview</p>", "language": "en"},
        )
        request.user = User.objects.create_superuser(
            username="preview-category-admin",
            email="preview-category@example.com",
            password="test",
        )

        response = self.model_admin.body_preview_view(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Select an article category", response.content.decode())

    def test_css_classes_uses_category_article_template(self):
        theme = Theme.objects.create(name="CSS theme", slug="css-theme", is_active=True)
        template = ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.PARENT_ARTICLE,
            name="CSS article",
            slug="css-article",
            css_classes=["card", "card-body", "lead"],
        )
        category = Category.objects.create(
            title="CSS category",
            slug="css-category",
            description="CSS category",
            article_theme_template=template,
        )
        request = RequestFactory().get(
            "/admin/blog_manager/article/css-classes/",
            {"category_id": category.pk},
        )
        request.user = User.objects.create_superuser(
            username="css-admin",
            email="css@example.com",
            password="test",
        )

        response = self.model_admin.css_classes_view(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["classes"], ["card", "card-body", "lead"])
        self.assertEqual(payload["template"]["id"], template.pk)

    def test_css_classes_requires_a_category(self):
        request = RequestFactory().get("/admin/blog_manager/article/css-classes/")
        request.user = User.objects.create_superuser(
            username="css-category-admin",
            email="css-category@example.com",
            password="test",
        )

        response = self.model_admin.css_classes_view(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Select an article category", response.content.decode())

    @patch("apps.blog_manager.article_preview.get_article_context", return_value={})
    @patch("apps.blog_manager.article_preview.get_article_template")
    @patch("apps.blog_manager.article_preview.render_to_string")
    def test_body_preview_wraps_body_and_adds_isolation_script(
        self,
        render_to_string,
        get_template,
        _get_context,
    ):
        get_template.return_value = SimpleNamespace(
            theme=SimpleNamespace(slug="preview-theme"),
            slug="article",
        )
        article = SimpleNamespace(body="")
        _get_context.return_value = {"article": article}
        render_to_string.side_effect = lambda _name, context: (
            "<!doctype html><html><body><main><div>"
            + context["article"].body
            + "</div></main></body></html>"
        )
        request = RequestFactory().get("/")
        request.user = self.request.user

        rendered = render_article_body_preview(
            request,
            article,
            '<p class="lead">Preview body</p>',
        )

        self.assertIn('<p class="lead">Preview body</p>', rendered)
        self.assertIn("createTreeWalker", rendered)
        self.assertIn("hideOutsideBoundary", rendered)
        self.assertIn("MutationObserver", rendered)
        self.assertIn('setProperty("display", "none", "important")', rendered)
        self.assertIn("wulver-article-preview-", rendered)

    def test_article_admin_loads_the_html_editor_assets(self):
        media = self.model_admin.media

        self.assertIn("blog_manager/js/article-body-editor.js", media._js)
        self.assertIn("admin/js/cms-link-browser.js", media._js)
        self.assertIn("blog_manager/js/article-content-images.js", media._js)
        self.assertIn(
            "blog_manager/css/article-body-editor.css",
            media._css["all"],
        )
        self.assertIn(
            "blog_manager/css/article-content-images.css",
            media._css["all"],
        )
        self.assertIn("admin/css/cms-link-browser.css", media._css["all"])
        self.assertTrue(any("htmlmixed" in str(path) for path in media._js))
        self.assertTrue(any("beautify-html" in str(path) for path in media._js))

    def test_html_field_preserves_classes_attributes_and_structure(self):
        form = self.model_admin.get_form(self.request)()
        html = (
            '<section class="hero custom-grid" data-module="article-hero">\n'
            '    <div class="hero__content" style="--columns: 2">\n'
            '        <p class="lead">Exact <span data-kind="accent">HTML</span></p>\n'
            '    </div>\n'
            '</section>'
        )

        self.assertEqual(form.fields["body_en"].clean(html), html)

    def test_site_link_browser_returns_localized_article_urls(self):
        category = Category.objects.create(
            title="Automation",
            slug="automation",
            description="Automation",
        )
        article = Article.objects.create(
            title="English title",
            title_uk="Українська назва",
            slug="localized-article",
            description="Description",
            intro="Intro",
            body="Body",
            category=category,
            is_published=True,
        )
        request = RequestFactory().get(
            "/admin/blog_manager/article/cms-link-options/",
            {"type": "article", "q": "Українська", "language": "uk"},
        )
        request.user = User.objects.create_superuser(
            username="article-link-admin",
            email="article-links@example.com",
            password="test",
        )

        response = self.model_admin.cms_link_options_view(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["items"][0]["id"], article.pk)
        self.assertEqual(data["items"][0]["title"], "Українська назва")
        self.assertEqual(
            data["items"][0]["url"],
            "/uk/automation/localized-article/",
        )
        self.assertEqual(data["items"][0]["reference"], f"article:{article.pk}")

    def test_site_link_browser_localizes_page_url(self):
        page = Page.objects.create(
            title="About",
            title_uk="Про нас",
            slug="about",
            description="About page",
            is_published=True,
        )
        request = RequestFactory().get(
            "/admin/blog_manager/article/cms-link-options/",
            {"type": "page", "q": "Про нас", "language": "uk"},
        )
        request.user = User.objects.create_superuser(
            username="page-link-admin",
            email="page-links@example.com",
            password="test",
        )

        response = self.model_admin.cms_link_options_view(request)
        data = json.loads(response.content)

        self.assertEqual(data["items"][0]["id"], page.pk)
        self.assertEqual(data["items"][0]["url"], "/uk/about/")

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.blog_manager.admin.OpenAI")
    def test_ai_editor_replaces_selected_text_only(self, openai_class):
        openai_class.return_value.responses.create.return_value = SimpleNamespace(
            output_text="```html\n<strong>Improved text</strong>\n```"
        )
        request = RequestFactory().post(
            "/admin/blog_manager/article/ai-edit-text/",
            {
                "selected_text": "Original text",
                "text_prompt": "Make it concise and bold HTML",
            },
        )
        request.user = self.request.user

        response = self.model_admin.ai_edit_text_view(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["text"], "<strong>Improved text</strong>")
        prompt_text = openai_class.return_value.responses.create.call_args.kwargs["input"]
        self.assertIn("Original text", prompt_text)
        self.assertIn("Make it concise and bold HTML", prompt_text)


class BlogSettingsSchemaTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/blog/", HTTP_HOST="localhost")
        self.site_settings = SiteSettings.get_solo()
        self.site_settings.default_schema_graph = {
            "@context": "https://schema.org",
            "@type": "WebPage",
        }
        self.site_settings.save()
        self.blog_settings = BlogSettings.get_solo()
        self.blog_settings.default_category_schema_graph = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
        }
        self.blog_settings.default_article_schema_graph = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
        }
        self.blog_settings.save()

    def test_uses_separate_category_and_article_schema_defaults(self):
        category = Category(title="News", slug="news", schema_graph={})
        article = Article(title="Update", slug="update", schema_graph={})

        category_schema = build_schema_graph(
            self.request,
            self.site_settings,
            seo_object=category,
        )
        article_schema = build_schema_graph(
            self.request,
            self.site_settings,
            seo_object=article,
        )

        self.assertEqual(category_schema["@type"], "CollectionPage")
        self.assertEqual(article_schema["@type"], "BlogPosting")

    def test_object_schema_overrides_blog_and_core_defaults(self):
        category = Category(
            title="News",
            slug="news",
            schema_graph={"@type": "CustomCategorySchema"},
        )

        schema = build_schema_graph(
            self.request,
            self.site_settings,
            seo_object=category,
        )

        self.assertEqual(schema["@type"], "CustomCategorySchema")

    def test_article_schema_is_generated_from_localized_article_fields(self):
        self.site_settings.site_url = "https://example.com"
        self.site_settings.person_name = "Article Author"
        self.site_settings.organization_name = "Example Publisher"
        self.site_settings.save()
        category = Category.objects.create(
            title_en="AI & Automation",
            title_uk="ШІ та автоматизація",
            slug="ai-automation",
            description="Category description",
            intro="Category intro",
        )
        article = Article.objects.create(
            title_en="English headline",
            title_uk="Український заголовок",
            slug="localized-article",
            description_en="English description",
            description_uk="Український опис",
            keywords="Codex, Ubuntu",
            preview_image="post/previews/article-cover.jpg",
            intro="Intro",
            body="Body",
            category=category,
        )
        article.tags.add(Tag.objects.create(title="WordPress", slug="wordpress"))
        request = RequestFactory().get(
            "/uk/ai-automation/localized-article/?utm_source=test",
            HTTP_HOST="localhost",
        )
        request.LANGUAGE_CODE = "uk"

        with override("uk"):
            schema = build_schema_graph(
                request,
                self.site_settings,
                seo_object=article,
            )

        self.assertEqual(schema["@type"], "BlogPosting")
        self.assertEqual(schema["headline"], "Український заголовок")
        self.assertEqual(schema["description"], "Український опис")
        self.assertEqual(schema["inLanguage"], "uk")
        self.assertEqual(schema["articleSection"], "ШІ та автоматизація")
        self.assertEqual(
            schema["mainEntityOfPage"]["@id"],
            "http://localhost/uk/ai-automation/localized-article/",
        )
        self.assertEqual(
            schema["image"],
            ["http://localhost/media/post/previews/article-cover.jpg"],
        )
        self.assertIn("datePublished", schema)
        self.assertIn("dateModified", schema)
        self.assertEqual(schema["author"]["name"], "Article Author")
        self.assertEqual(schema["publisher"]["name"], "Example Publisher")
        self.assertEqual(schema["keywords"], ["Codex", "Ubuntu", "WordPress"])
        self.assertEqual(
            schema["about"],
            [{"@type": "Thing", "name": "WordPress"}],
        )

    def test_article_custom_schema_is_merged_after_generated_values(self):
        article = Article.objects.create(
            title="Generated headline",
            slug="custom-schema-article",
            description="Generated description",
            intro="Intro",
            body="Body",
            schema_graph={
                "@type": "HowTo",
                "headline": "Manual headline",
                "proficiencyLevel": "Beginner",
            },
        )

        schema = build_schema_graph(
            self.request,
            self.site_settings,
            seo_object=article,
        )

        self.assertEqual(schema["@type"], "HowTo")
        self.assertEqual(schema["headline"], "Manual headline")
        self.assertEqual(schema["proficiencyLevel"], "Beginner")
        self.assertEqual(schema["inLanguage"], "en")
        self.assertIn("datePublished", schema)
        self.assertIn("dateModified", schema)


class BlogContextProcessorTests(TestCase):
    def test_latest_blog_articles_uses_limit_and_ignores_future_or_unpublished_articles(self):
        now = timezone.now()
        category = Category.objects.create(
            title="News",
            slug="news",
            description="News category",
            intro="News intro",
        )
        old_article = Article.objects.create(
            title="Old article",
            slug="old-article",
            description="Old description",
            intro="Old intro",
            body="Old body",
            category=category,
            publish=now - timezone.timedelta(days=2),
        )
        fresh_article = Article.objects.create(
            title="Fresh article",
            slug="fresh-article",
            description="Fresh description",
            intro="Fresh intro",
            body="Fresh body",
            category=category,
            publish=now - timezone.timedelta(days=1),
        )
        Article.objects.create(
            title="Future article",
            slug="future-article",
            description="Future description",
            intro="Future intro",
            body="Future body",
            category=category,
            publish=now + timezone.timedelta(days=1),
        )
        Article.objects.create(
            title="Unpublished article",
            slug="unpublished-article",
            description="Unpublished description",
            intro="Unpublished intro",
            body="Unpublished body",
            category=category,
            is_published=False,
            publish=now,
        )

        articles = list(get_latest_blog_articles(2))

        self.assertEqual(articles, [fresh_article, old_article])

    def test_context_processor_uses_distinct_latest_blog_articles_name(self):
        context = blog_context(RequestFactory().get("/"))

        self.assertIn("latest_blog_articles", context)
        self.assertNotIn("articles", context)

    def test_tag_cloud_contains_used_tags_with_article_counts(self):
        category = Category.objects.create(
            title="News",
            slug="news",
            description="News category",
            intro="News intro",
        )
        python = Tag.objects.create(title="Python", slug="python")
        django = Tag.objects.create(title="Django", slug="django")
        unused = Tag.objects.create(title="Unused", slug="unused")
        old_article = Article.objects.create(
            title="Old article",
            slug="tag-old-article",
            description="Old description",
            intro="Old intro",
            body="Old body",
            category=category,
        )
        fresh_article = Article.objects.create(
            title="Fresh article",
            slug="tag-fresh-article",
            description="Fresh description",
            intro="Fresh intro",
            body="Fresh body",
            category=category,
        )
        old_article.tags.add(python)
        fresh_article.tags.add(python, django)

        context = blog_context(RequestFactory().get("/"))
        tags = context["tags_cloud"]

        self.assertEqual([tag.title for tag in tags], ["Python", "Django"])
        self.assertNotIn(unused, tags)
        self.assertEqual(tags[0].article_count, 2)
        self.assertEqual(tags[1].article_count, 1)
        self.assertTrue(all(not hasattr(tag, "random_class") for tag in tags))
        self.assertTrue(all(not hasattr(tag, "size_class") for tag in tags))
