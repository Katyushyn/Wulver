from django.db import migrations, models


def add_health_exclusion(apps, schema_editor):
    AnalyticsSettings = apps.get_model("analytics_manager", "AnalyticsSettings")
    configuration = AnalyticsSettings.objects.filter(pk=1).first()
    if not configuration:
        return
    prefix = "/ai-assistant/health/"
    values = [
        line.strip()
        for line in configuration.excluded_path_prefixes.splitlines()
        if line.strip()
    ]
    if prefix not in values:
        values.append(prefix)
        configuration.excluded_path_prefixes = "\n".join(values)
        configuration.save(update_fields=["excluded_path_prefixes"])


class Migration(migrations.Migration):
    dependencies = [
        ("analytics_manager", "0002_create_default_analyticssettings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="analyticssettings",
            name="excluded_path_prefixes",
            field=models.TextField(
                blank=True,
                default="/admin/\n/static/\n/media/\n/rosetta/\n/ai-assistant/health/",
                help_text="One local URL prefix per line.",
                verbose_name="Excluded URL prefixes",
            ),
        ),
        migrations.RunPython(
            add_health_exclusion,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

