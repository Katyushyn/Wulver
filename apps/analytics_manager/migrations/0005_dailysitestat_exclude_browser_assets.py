from django.db import migrations, models


EXCLUDED_PATHS = ("/favicon.ico", "/favicon.png", "/apple-touch-icon")


def add_browser_asset_exclusions(apps, schema_editor):
    AnalyticsSettings = apps.get_model("analytics_manager", "AnalyticsSettings")
    configuration = AnalyticsSettings.objects.filter(pk=1).first()
    if configuration:
        values = [
            line.strip()
            for line in configuration.excluded_path_prefixes.splitlines()
            if line.strip()
        ]
        changed = False
        for prefix in EXCLUDED_PATHS:
            if prefix not in values:
                values.append(prefix)
                changed = True
        if changed:
            configuration.excluded_path_prefixes = "\n".join(values)
            configuration.save(update_fields=["excluded_path_prefixes"])

    DailyPageStat = apps.get_model("analytics_manager", "DailyPageStat")
    DailyUniqueVisitor = apps.get_model("analytics_manager", "DailyUniqueVisitor")
    Visit = apps.get_model("analytics_manager", "Visit")
    for prefix in EXCLUDED_PATHS:
        DailyPageStat.objects.filter(path__startswith=prefix).delete()
        DailyUniqueVisitor.objects.filter(path__startswith=prefix).delete()
        Visit.objects.filter(path__startswith=prefix).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("analytics_manager", "0004_analyticssettings_collection_mode"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailySiteStat",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date", models.DateField(unique=True, verbose_name="Date")),
                ("views", models.PositiveBigIntegerField(default=0, verbose_name="Views")),
                (
                    "unique_visitors",
                    models.PositiveBigIntegerField(
                        default=0, verbose_name="Unique visitors"
                    ),
                ),
            ],
            options={
                "verbose_name": "Daily site statistic",
                "verbose_name_plural": "Daily site statistics",
                "ordering": ("-date",),
            },
        ),
        migrations.AlterField(
            model_name="analyticssettings",
            name="excluded_path_prefixes",
            field=models.TextField(
                blank=True,
                default=(
                    "/admin/\n/static/\n/media/\n/rosetta/\n/ai-assistant/health/\n"
                    "/favicon.ico\n/favicon.png\n/apple-touch-icon"
                ),
                help_text="One local URL prefix per line.",
                verbose_name="Excluded URL prefixes",
            ),
        ),
        migrations.RunPython(
            add_browser_asset_exclusions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

