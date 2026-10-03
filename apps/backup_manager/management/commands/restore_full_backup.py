from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.backup_manager.models import BackupSnapshot
from apps.backup_manager.services import restore_backup_archive
from apps.backup_manager.services.jobs import read_and_remove_password_file


class Command(BaseCommand):
    help = "Restore one encrypted full-site Wulver backup."

    def add_arguments(self, parser):
        parser.add_argument("snapshot_id")
        parser.add_argument("--password-file", required=True)

    def handle(self, *args, **options):
        try:
            snapshot = BackupSnapshot.objects.get(pk=options["snapshot_id"])
            password = read_and_remove_password_file(options["password_file"])
            restore_backup_archive(snapshot, password)
        except Exception as error:
            try:
                snapshot = BackupSnapshot.objects.get(pk=options["snapshot_id"])
                snapshot.status = BackupSnapshot.Status.FAILED
                snapshot.error_message = str(error)
                snapshot.completed_at = timezone.now()
                snapshot.save()
            except Exception:
                pass
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Backup {snapshot.pk} restored."))
