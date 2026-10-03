from django.test import SimpleTestCase
from django.template import Engine

from apps.theme_manager.template_formatter import format_template_code


class TemplateFormatterTest(SimpleTestCase):
    def test_formats_nested_html_and_django_blocks(self):
        code = (
            "{% if items %}<ul><li>{{ title }}</li>"
            "{% for item in items %}<li>{{ item }}</li>{% endfor %}"
            "</ul>{% endif %}"
        )

        formatted = format_template_code(code)

        self.assertEqual(
            formatted,
            "{% if items %}\n"
            "    <ul>\n"
            "        <li>\n"
            "            {{ title }}\n"
            "        </li>\n"
            "        {% for item in items %}\n"
            "            <li>\n"
            "                {{ item }}\n"
            "            </li>\n"
            "        {% endfor %}\n"
            "    </ul>\n"
            "{% endif %}\n",
        )

    def test_preserves_django_tags_inside_html_attributes(self):
        code = (
            '<li{% if item.active %} class="active"{% endif %}>'
            '<a href="{{ item.url }}">{{ item.title }}</a></li>'
        )

        formatted = format_template_code(code)

        self.assertIn(
            '<li{% if item.active %} class="active"{% endif %}>',
            formatted,
        )
        self.assertIn('<a href="{{ item.url }}">', formatted)
        Engine.get_default().from_string(formatted)

    def test_preserves_raw_script_content(self):
        code = (
            "<script>\n"
            "if (value < 10) {\n"
            "  console.log('{{ value }}');\n"
            "}\n"
            "</script>"
        )

        formatted = format_template_code(code)

        self.assertIn("if (value < 10) {", formatted)
        self.assertIn("  console.log('{{ value }}');", formatted)
        self.assertEqual(formatted.count("<script>"), 1)
        self.assertEqual(formatted.count("</script>"), 1)

    def test_formatter_is_idempotent(self):
        code = (
            "{% block main %}<main><section><h1>{{ title }}</h1>"
            "</section></main>{% endblock %}"
        )

        first = format_template_code(code)
        second = format_template_code(first)

        self.assertEqual(second, first)

    def test_formatter_is_idempotent_for_indented_raw_script_content(self):
        code = (
            "<main>\n"
            "    <script type=\"application/ld+json\">\n"
            "        {{ schema_graph|safe }}\n"
            "\n"
            "    </script>\n"
            "</main>"
        )

        first = format_template_code(code)
        second = format_template_code(first)
        third = format_template_code(second)

        self.assertEqual(second, first)
        self.assertEqual(third, first)
        self.assertIn(
            "        {{ schema_graph|safe }}\n"
            "    </script>",
            first,
        )
