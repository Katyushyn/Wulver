from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics_manager.models import AnalyticsSettings, DailyUniqueVisitor, Visit


class Command(BaseCommand):
    help = "Remove detailed analytics data older than the configured retention period."

    def handle(self, **options):
        configuration = AnalyticsSettings.get_solo()
        cutoff = timezone.now() - timedelta(days=configuration.retention_days)
        visits, _details = Visit.objects.filter(created_at__lt=cutoff).delete()
        unique_cutoff = timezone.localdate() - timedelta(days=1)
        unique_rows, _details = DailyUniqueVisitor.objects.filter(
            date__lt=unique_cutoff
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {visits} visits and {unique_rows} expired unique-visitor rows."
            )
        )

