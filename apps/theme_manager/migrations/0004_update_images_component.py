from django.db import migrations


def update_images_component(apps, schema_editor):
    from apps.theme_manager.defaults.template_components import (
        DEFAULT_TEMPLATE_COMPONENTS,
    )

    component = next(
        item for item in DEFAULT_TEMPLATE_COMPONENTS
        if item["slug"] == "images"
    )
    defaults = component.copy()
    slug = defaults.pop("slug")

    TemplateComponent = apps.get_model("theme_manager", "TemplateComponent")
    TemplateComponent.objects.update_or_create(slug=slug, defaults=defaults)


class Migration(migrations.Migration):
    dependencies = [
        ("theme_manager", "0003_seed_article_navigation_components"),
    ]

    operations = [
        migrations.RunPython(update_images_component, migrations.RunPython.noop),
    ]
