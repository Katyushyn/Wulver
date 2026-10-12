from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.analytics_manager.models import DailyPageStat, DailySiteStat


class AnalyticsDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="analytics-dashboard-admin",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_admin_index_contains_analytics_summary_and_fourteen_days(self):
        today = timezone.localdate()
        DailyPageStat.objects.create(
            date=today,
            path="/",
            views=12,
            unique_visitors=7,
        )
        DailyPageStat.objects.create(
            date=today - timedelta(days=1),
            path="/article/",
            views=5,
            unique_visitors=3,
        )
        DailySiteStat.objects.create(
            date=today,
            views=12,
            unique_visitors=4,
        )
        DailySiteStat.objects.create(
            date=today - timedelta(days=1),
            views=5,
            unique_visitors=2,
        )

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        overview = response.context["analytics_overview"]
        self.assertEqual(overview["today_views"], 12)
        self.assertEqual(overview["today_visitors"], 4)
        self.assertEqual(overview["month_views"], 17)
        self.assertEqual(len(overview["chart"]), 14)
        self.assertContains(response, "Site analytics")
        self.assertContains(response, "wulver-chart")

    def test_non_superuser_does_not_receive_sensitive_analytics_panel(self):
        self.user.is_superuser = False
        self.user.save(update_fields=["is_superuser"])

        response = self.client.get(reverse("admin:index"))

        self.assertIsNone(response.context["analytics_overview"])
        self.assertNotContains(response, "Site analytics")

