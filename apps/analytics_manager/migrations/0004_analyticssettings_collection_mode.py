from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics_manager", "0003_exclude_health_endpoint"),
    ]

    operations = [
        migrations.AddField(
            model_name="analyticssettings",
            name="collection_mode",
            field=models.CharField(
                choices=[
                    ("compact", "Compact — daily totals only"),
                    ("detailed", "Detailed — record every visit"),
                ],
                default="compact",
                help_text=(
                    "Compact mode stores only daily totals. Detailed mode additionally "
                    "stores every page view for the configured retention period."
                ),
                max_length=10,
                verbose_name="Collection mode",
            ),
        ),
    ]

