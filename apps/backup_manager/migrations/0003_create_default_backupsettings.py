from django.db import migrations


def create_default_backup_settings(apps, schema_editor):
    BackupSettings = apps.get_model("backup_manager", "BackupSettings")
    BackupSettings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [
        ("backup_manager", "0002_backupsnapshot_storage_root"),
    ]

    operations = [
        migrations.RunPython(
            create_default_backup_settings,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
