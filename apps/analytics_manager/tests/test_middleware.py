from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpResponse
from datetime import timedelta

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.analytics_manager.middleware import VisitTrackingMiddleware
from apps.analytics_manager.models import (
    AnalyticsSettings,
    DailyPageStat,
    DailySiteStat,
    Visit,
)


@override_settings(TRUST_X_FORWARDED_FOR=False)
class VisitTrackingMiddlewareTests(TestCase):
    def setUp(self):
        cache.delete("analytics:configuration")
        cache.delete("analytics:retention-cleanup")
        self.factory = RequestFactory()
        self.configuration = AnalyticsSettings.get_solo()
        self.configuration.collection_mode = AnalyticsSettings.CollectionMode.DETAILED
        self.configuration.save(update_fields=["collection_mode"])
        self.middleware = VisitTrackingMiddleware(lambda request: HttpResponse("OK"))

    def tearDown(self):
        cache.delete("analytics:configuration")
        cache.delete("analytics:retention-cleanup")

    def request(self, path="/article/?tag=django&token=secret", **meta):
        request = self.factory.get(path, **meta)
        request.user = AnonymousUser()
        return request

    def test_records_hashed_visit_and_daily_statistics(self):
        request = self.request(
            REMOTE_ADDR="203.0.113.25",
            HTTP_USER_AGENT="Test browser",
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        visit = Visit.objects.get()
        self.assertEqual(visit.path, "/article/")
        self.assertEqual(visit.query_string, "tag=django&token=%5Bredacted%5D")
        self.assertIsNone(visit.ip_address)
        self.assertEqual(len(visit.ip_hash), 64)
        stat = DailyPageStat.objects.get(path="/article/")
        self.assertEqual(stat.views, 1)
        self.assertEqual(stat.unique_visitors, 1)
        site_stat = DailySiteStat.objects.get()
        self.assertEqual(site_stat.views, 1)
        self.assertEqual(site_stat.unique_visitors, 1)

    def test_compact_mode_does_not_create_individual_visit_rows(self):
        self.configuration.collection_mode = AnalyticsSettings.CollectionMode.COMPACT
        self.configuration.save(update_fields=["collection_mode"])

        self.middleware(
            self.request(
                "/compact/",
                REMOTE_ADDR="203.0.113.25",
                HTTP_USER_AGENT="Test browser",
            )
        )

        self.assertFalse(Visit.objects.exists())
        stat = DailyPageStat.objects.get(path="/compact/")
        self.assertEqual(stat.views, 1)
        self.assertEqual(stat.unique_visitors, 1)
        self.assertEqual(DailySiteStat.objects.get().unique_visitors, 1)

    def test_same_visitor_is_unique_once_but_each_view_is_counted(self):
        meta = {"REMOTE_ADDR": "203.0.113.25", "HTTP_USER_AGENT": "Test browser"}
        self.middleware(self.request("/article/", **meta))
        self.middleware(self.request("/article/", **meta))

        stat = DailyPageStat.objects.get(path="/article/")
        self.assertEqual(stat.views, 2)
        self.assertEqual(stat.unique_visitors, 1)
        site_stat = DailySiteStat.objects.get()
        self.assertEqual(site_stat.views, 2)
        self.assertEqual(site_stat.unique_visitors, 1)

    def test_excludes_admin_static_and_known_bots(self):
        self.middleware(self.request("/admin/", REMOTE_ADDR="203.0.113.1"))
        self.middleware(self.request("/static/site.css", REMOTE_ADDR="203.0.113.1"))
        self.middleware(
            self.request(
                "/public/",
                REMOTE_ADDR="203.0.113.1",
                HTTP_USER_AGENT="Googlebot",
            )
        )

        self.assertFalse(Visit.objects.exists())

    def test_favicons_are_not_counted(self):
        for path in ("/favicon.ico", "/favicon.png", "/apple-touch-icon.png"):
            self.middleware(self.request(path, REMOTE_ADDR="203.0.113.25"))

        self.assertFalse(DailyPageStat.objects.exists())
        self.assertFalse(DailySiteStat.objects.exists())

    def test_ip_storage_can_be_disabled(self):
        self.configuration.ip_storage_mode = AnalyticsSettings.IPStorageMode.NONE
        self.configuration.save(update_fields=["ip_storage_mode"])

        self.middleware(
            self.request(
                "/privacy/",
                REMOTE_ADDR="203.0.113.25",
                HTTP_USER_AGENT="Test browser",
            )
        )

        visit = Visit.objects.get()
        self.assertIsNone(visit.ip_address)
        self.assertEqual(visit.ip_hash, "")
        self.assertEqual(visit.visitor_hash, "")

    def test_staff_visit_is_excluded_by_default(self):
        request = self.request("/", REMOTE_ADDR="203.0.113.25")
        request.user = get_user_model().objects.create_user(
            username="staff", is_staff=True
        )

        self.middleware(request)

        self.assertFalse(Visit.objects.exists())

    def test_old_detailed_visits_are_cleaned_once_tracking_runs(self):
        old_visit = Visit.objects.create(path="/expired/", status_code=200)
        Visit.objects.filter(pk=old_visit.pk).update(
            created_at=timezone.now()
            - timedelta(days=self.configuration.retention_days + 1)
        )

        self.middleware(self.request("/current/", REMOTE_ADDR="203.0.113.25"))

        self.assertFalse(Visit.objects.filter(pk=old_visit.pk).exists())
        self.assertTrue(Visit.objects.filter(path="/current/").exists())

