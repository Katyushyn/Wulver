from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.analytics_manager.models import AnalyticsSettings, DailyPageStat, Visit


class CleanupAnalyticsTests(TestCase):
    def test_removes_expired_visits_but_preserves_daily_totals(self):
        configuration = AnalyticsSettings.get_solo()
        configuration.retention_days = 30
        configuration.save(update_fields=["retention_days"])
        old_visit = Visit.objects.create(path="/old/", status_code=200)
        Visit.objects.filter(pk=old_visit.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )
        DailyPageStat.objects.create(
            date=timezone.localdate() - timedelta(days=31),
            path="/old/",
            views=4,
            unique_visitors=3,
        )

        call_command("cleanup_analytics")

        self.assertFalse(Visit.objects.filter(pk=old_visit.pk).exists())
        self.assertTrue(DailyPageStat.objects.filter(path="/old/").exists())

