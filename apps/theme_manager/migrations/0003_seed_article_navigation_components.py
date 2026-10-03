from django.db import migrations


COMPONENTS = (
    {
        "name": "Previous article",
        "slug": "previous-article",
        "category": "Navigation",
        "icon": "keyboard_double_arrow_left",
        "sort_order": 40,
        "description": "Button linking to the previous article prepared by the article detail view.",
        "code": """{% load i18n %}
{% if prev_article %}
    <a href="{% url 'blog:post' category_slug=prev_article.category.slug post_slug=prev_article.slug %}"
       class="btn btn-primary w-100 d-flex align-items-center justify-content-start">
        <i class="fas fa-angle-double-left mr-2" aria-hidden="true"></i>
        <span>{% trans "Previous template" %}: {{ prev_article.title }}</span>
    </a>
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected previous-article link or button into a dynamic Django article navigation button.
- Preserve the selected wrapper, button classes, alignment, icons, spans, aria attributes, and layout.
- Use the context variable prev_article.
- Wrap the complete button in {% if prev_article %}.
- Build the URL with {% url 'blog:post' category_slug=prev_article.category.slug post_slug=prev_article.slug %}.
- Use prev_article.title for the visible article title.
- Keep translated static labels with {% load i18n %} and {% trans %}.
- Do not include next_article markup.
- Return only the converted template fragment.""",
    },
    {
        "name": "Next article",
        "slug": "next-article",
        "category": "Navigation",
        "icon": "keyboard_double_arrow_right",
        "sort_order": 41,
        "description": "Button linking to the next article prepared by the article detail view.",
        "code": """{% load i18n %}
{% if next_article %}
    <a href="{% url 'blog:post' category_slug=next_article.category.slug post_slug=next_article.slug %}"
       class="btn btn-primary w-100 d-flex align-items-center justify-content-end">
        <span>{% trans "Next template" %}: {{ next_article.title }}</span>
        <i class="fas fa-angle-double-right ml-2" aria-hidden="true"></i>
    </a>
{% endif %}""",
        "ai_conversion_prompt": """Convert the selected next-article link or button into a dynamic Django article navigation button.
- Preserve the selected wrapper, button classes, alignment, icons, spans, aria attributes, and layout.
- Use the context variable next_article.
- Wrap the complete button in {% if next_article %}.
- Build the URL with {% url 'blog:post' category_slug=next_article.category.slug post_slug=next_article.slug %}.
- Use next_article.title for the visible article title.
- Keep translated static labels with {% load i18n %} and {% trans %}.
- Do not include prev_article markup.
- Return only the converted template fragment.""",
    },
)


def seed_article_navigation_components(apps, schema_editor):
    TemplateComponent = apps.get_model("theme_manager", "TemplateComponent")

    for component in COMPONENTS:
        defaults = component.copy()
        slug = defaults.pop("slug")
        TemplateComponent.objects.update_or_create(slug=slug, defaults=defaults)


def remove_article_navigation_components(apps, schema_editor):
    TemplateComponent = apps.get_model("theme_manager", "TemplateComponent")
    TemplateComponent.objects.filter(
        slug__in=[component["slug"] for component in COMPONENTS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("theme_manager", "0002_seed_default_components"),
    ]

    operations = [
        migrations.RunPython(
            seed_article_navigation_components,
            remove_article_navigation_components,
        ),
    ]
