from django.db import migrations


def create_default_settings(apps, schema_editor):
    AnalyticsSettings = apps.get_model("analytics_manager", "AnalyticsSettings")
    AnalyticsSettings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [
        ("analytics_manager", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_default_settings,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

