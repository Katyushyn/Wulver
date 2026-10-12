"""Install only the minimum system theme in a new, empty database."""
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.core_manager.models import Page, SiteSettings
from apps.theme_manager.models import Theme, ThemeTemplate, TemplateType


BASE = '''{% load i18n %}<!doctype html>
<html lang="{{ lang }}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title><meta name="description" content="{{ description }}">
<meta name="robots" content="{{ robots }}">
{% if canonical_url %}<link rel="canonical" href="{{ canonical_url }}">{% endif %}
{{ alternate_links }}{% if schema_graph %}<script type="application/ld+json">{{ schema_graph }}</script>{% endif %}
<style>body{font-family:system-ui,sans-serif;max-width:60rem;margin:4rem auto;padding:0 1.5rem;line-height:1.6}a{color:#245dcc}</style>
</head><body>{% block content %}{% endblock %}</body></html>'''
HOME = '''{% extends "wulver-system/base.html" %}{% load i18n %}
{% block content %}<h1>Wulver</h1><p>{% trans "Your site is ready." %}</p>
<p><a href="{% url 'admin:index' %}">{% trans "Administration" %}</a></p>{% endblock %}'''
ERROR = '''{% extends "wulver-system/base.html" %}{% load i18n %}
{% block content %}<h1>{{ error_title }}</h1><p>{{ error_message }}</p>
<a href="{% url 'core_manager:home' %}">{% trans "Home" %}</a>{% endblock %}'''


class Command(BaseCommand):
    help = 'Create minimal system pages, without demo content. Refuses an existing site.'

    def handle(self, **options):
        if Theme.objects.exists() or Page.objects.exists():
            raise CommandError('Existing site detected; bootstrap will not overwrite it.')
        directory = Path(settings.BASE_DIR) / 'templates' / 'wulver-system'
        if directory.exists():
            raise CommandError('System template directory already exists.')
        directory.mkdir(parents=True)
        with transaction.atomic():
            theme = Theme.objects.create(name='Wulver System', slug='wulver-system', is_active=True)
            records = {}
            for slug, kind, code in (
                ('base', TemplateType.BASE_TEMPLATE, BASE),
                ('home', TemplateType.CHILDREN_PAGE, HOME),
                ('404', TemplateType.ERROR_TEMPLATE, ERROR),
            ):
                records[slug] = ThemeTemplate.objects.create(theme=theme, name=slug.title(), slug=slug, template_type=kind)
                (directory / f'{slug}.html').write_text(code)
            page = Page.objects.create(title='Home', title_en='Home', title_uk='Головна',
                slug='home', description='', template=records['home'])
            site = SiteSettings.get_solo()
            site.site_name = site.site_name_en = site.site_name_uk = 'Wulver'
            site.home_page = page
            site.error_404_template = records['404']
            site.save()
        self.stdout.write(self.style.SUCCESS('Minimal Wulver site created (no demo content).'))
