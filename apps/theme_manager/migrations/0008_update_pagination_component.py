from django.db import migrations


PAGINATION_CODE = """{% load i18n pagination %}
{% if page_obj and page_obj.paginator.num_pages > 1 %}
    {% elided_page_range page_obj as page_numbers %}
    <nav class="pagination-wrap" aria-label="{% trans 'Pagination' %}">
        <ul class="pagination">
            {% if page_obj.has_previous %}
                <li><a href="?page={{ page_obj.previous_page_number }}" rel="prev">{% trans "Previous" %}</a></li>
            {% endif %}

            {% for page_number in page_numbers %}
                {% if page_number == page_obj.paginator.ELLIPSIS %}
                    <li class="disabled"><span>{{ page_number }}</span></li>
                {% else %}
                    <li>
                        {% if page_number == page_obj.number %}
                            <span class="active" aria-current="page">{{ page_number }}</span>
                        {% else %}
                            <a href="?page={{ page_number }}">{{ page_number }}</a>
                        {% endif %}
                    </li>
                {% endif %}
            {% endfor %}

            {% if page_obj.has_next %}
                <li><a href="?page={{ page_obj.next_page_number }}" rel="next">{% trans "Next" %}</a></li>
            {% endif %}
        </ul>
    </nav>
{% endif %}"""


PAGINATION_AI_PROMPT = """Convert the selected pagination markup into Django pagination using page_obj.
- Preserve wrappers, classes, icons, aria attributes, rel attributes, and visual structure.
- Load i18n and pagination, then use elided_page_range to build page_numbers.
- Use page_obj.has_previous, page_obj.previous_page_number, page_obj.number, page_obj.has_next, and page_obj.next_page_number.
- Render paginator.ELLIPSIS as disabled text without a link.
- Wrap the result in an if that only renders when page_obj exists and page_obj.paginator.num_pages > 1.
- Keep the current page active state in the same visual style as the selected markup."""


def update_pagination_component(apps, schema_editor):
    TemplateComponent = apps.get_model("theme_manager", "TemplateComponent")
    TemplateComponent.objects.filter(slug="pagination").update(
        code=PAGINATION_CODE,
        ai_conversion_prompt=PAGINATION_AI_PROMPT,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("theme_manager", "0007_normalize_tag_component_search_links"),
    ]

    operations = [
        migrations.RunPython(
            update_pagination_component,
            migrations.RunPython.noop,
        ),
    ]
