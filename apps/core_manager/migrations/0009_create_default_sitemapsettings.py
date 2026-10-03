from django.db import migrations


def create_default_sitemap_settings(apps, schema_editor):
    SitemapSettings = apps.get_model("core_manager", "SitemapSettings")
    SitemapSettings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [
        ("core_manager", "0008_alter_sitesettings_canonical_allowed_params"),
    ]

    operations = [
        migrations.RunPython(
            create_default_sitemap_settings,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
