from django.db import migrations


SEARCH_LINK = "{% url 'core_manager:search' %}?tag={{ item.slug }}"
LEGACY_LINKS = (
    "/search/?tag={{ item.slug }}",
    "/search?tag={{ item.slug }}",
    "{% url 'core_manager:tag_detail' tag_slug=item.slug %}",
)


def normalize_tag_links(apps, schema_editor):
    TemplateComponent = apps.get_model("theme_manager", "TemplateComponent")
    for component in TemplateComponent.objects.all().iterator():
        code = component.code
        for legacy_link in LEGACY_LINKS:
            code = code.replace(legacy_link, SEARCH_LINK)
        if code != component.code:
            component.code = code
            component.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [
        ("theme_manager", "0006_themetemplate_css_classes"),
    ]

    operations = [
        migrations.RunPython(normalize_tag_links, migrations.RunPython.noop),
    ]
