from apps.theme_manager.defaults.template_components import DEFAULT_TEMPLATE_COMPONENTS
from apps.theme_manager.models import TemplateComponent


def sync_template_components(stdout=None):
    created = 0
    updated = 0

    for component in DEFAULT_TEMPLATE_COMPONENTS:
        defaults = component.copy()
        slug = defaults.pop("slug")
        _component, was_created = TemplateComponent.objects.update_or_create(
            slug=slug,
            defaults=defaults,
        )

        if was_created:
            created += 1
        else:
            updated += 1

    result = {
        "created": created,
        "updated": updated,
        "total": len(DEFAULT_TEMPLATE_COMPONENTS),
    }

    if stdout:
        stdout.write(
            "Template components synced: "
            f"{created} created, {updated} updated, {result['total']} total."
        )

    return result
