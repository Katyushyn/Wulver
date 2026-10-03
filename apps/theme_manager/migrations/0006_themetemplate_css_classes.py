from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("theme_manager", "0005_alter_theme_templates_map"),
    ]

    operations = [
        migrations.AddField(
            model_name="themetemplate",
            name="css_classes",
            field=models.JSONField(blank=True, default=list, editable=False),
        ),
    ]
