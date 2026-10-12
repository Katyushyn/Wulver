from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from apps.ai_assistant.models import AssistantEventLog
from apps.blog_manager.models import Article
from apps.theme_manager.models import TemplateType, Theme, ThemeTemplate

from .dashboard_health import dashboard_health_context


class DashboardHealthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_superuser(
            username="health-admin",
            password="test-password",
        )
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user

    def tearDown(self):
        cache.clear()

    def test_returns_only_actionable_existing_problems(self):
        Article.objects.create(
            title="Missing images",
            slug="missing-images",
            description="Description",
            intro="Intro",
            body="Body",
            author=self.user,
        )
        AssistantEventLog.objects.create(
            event_type="api_error",
            message="Provider unavailable",
        )

        result = dashboard_health_context(self.request, refresh=True)
        titles = {item["title"] for item in result["warnings"]}

        self.assertIn("No completed backup", titles)
        self.assertIn("Published articles without complete optimized images", titles)
        self.assertIn("Recent AI assistant errors", titles)

    def test_cached_result_does_not_repeat_database_work(self):
        first = dashboard_health_context(self.request, refresh=True)

        with self.assertNumQueries(0):
            second = dashboard_health_context(self.request)

        self.assertEqual(first, second)

    def test_non_superuser_cannot_receive_health_details(self):
        self.user.is_superuser = False
        self.user.save(update_fields=["is_superuser"])

        self.assertIsNone(dashboard_health_context(self.request))

    @override_settings(OPENAI_API_KEY="   ")
    def test_missing_openai_key_is_warning(self):
        result = dashboard_health_context(self.request)
        warning = next(item for item in result['warnings'] if item['title'] == 'OpenAI API key is not configured')
        self.assertEqual(warning['severity'], 'warning')
        self.assertTrue(warning['url'].endswith('#env-OPENAI_API_KEY'))

    def test_openai_key_presence_is_not_cached_or_exposed(self):
        with override_settings(OPENAI_API_KEY=''):
            dashboard_health_context(self.request)
        with override_settings(OPENAI_API_KEY='private-test-credential'):
            result = dashboard_health_context(self.request)
        self.assertNotIn('OpenAI API key is not configured', {item['title'] for item in result['warnings']})
        self.assertNotIn('private-test-credential', str(result))

    def test_unconfigured_404_with_active_fallback_is_only_a_warning(self):
        theme = Theme.objects.create(name="Health theme", slug="health-theme", is_active=True)
        ThemeTemplate.objects.create(
            theme=theme,
            template_type=TemplateType.ERROR_TEMPLATE,
            name="404",
            slug="404",
            is_active=True,
        )

        result = dashboard_health_context(self.request, refresh=True)
        warning = next(
            item for item in result["warnings"]
            if item["title"] == "404 template is selected automatically"
        )

        self.assertEqual(warning["severity"], "warning")
        self.assertNotIn(
            "404 template is not available",
            {item["title"] for item in result["warnings"]},
        )

