"""Explicit local-only Story export for licensing review."""
import json
import re
from pathlib import Path
import zipfile
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db.models import FileField

MODELS = (
    'theme_manager.Theme', 'theme_manager.ThemeTemplate',
    'blog_manager.BlogSettings', 'blog_manager.Category', 'blog_manager.Tag',
    'blog_manager.Article', 'blog_manager.ArticleImage',
    'blog_manager.LatestArticlesModule', 'blog_manager.TagModule', 'blog_manager.ImageModule',
    'core_manager.Page', 'core_manager.SiteSettings', 'core_manager.SitemapSettings',
    'comments_manager.CommentSettings', 'comments_manager.CommentTemplate',
    'comments_manager.LatestCommentsModule', 'django_comments.Comment',
    'userprofile.UserProfile', 'userprofile.AuthenticationSettings',
    'userprofile.PersonalAccountTemplate', 'userprofile.AuthenticationTemplate',
    'userprofile.AuthenticationEmailTemplate',
)


class Command(BaseCommand):
    help = 'Export private Story demo (never passwords, sessions, API settings or leads).'

    def add_arguments(self, parser):
        parser.add_argument('output')

    def handle(self, output, **options):
        root = Path(settings.BASE_DIR)
        if list(apps.get_model('theme_manager.Theme').objects.values_list('slug', flat=True)) != ['story']:
            raise CommandError('Export requires the dedicated Story demo database.')
        objects = [obj for label in MODELS for obj in apps.get_model(label).objects.all()]
        records = json.loads(serializers.serialize('json', objects))
        for row in records:
            fields = row['fields']
            if row['model'] == 'core_manager.sitesettings':
                for key in ('site_domain', 'site_url', 'contact_email', 'contact_phone',
                            'google_analytics_id', 'google_tag_manager_id', 'github_reviews_repository',
                            'author_name', 'organization_name', 'person_name', 'person_job_title',
                            'same_as_links', 'twitter_handle'):
                    for variant in (key, key + '_en', key + '_uk'):
                        if variant in fields:
                            fields[variant] = ''
                fields.update(github_reviews_enabled=False, reviews_enabled=False,
                              default_schema_graph={}, maintenance_mode=False)
            if row['model'] == 'userprofile.userprofile':
                fields.update(prompt='', share_token=None, share_token_created=None)
            if row['model'] == 'django_comments.comment':
                fields.update(user_email='', user_url='', ip_address=None)
        users = []
        for user in get_user_model().objects.all():
            users.append({'source_id': user.pk, 'administrator': user.is_superuser,
                          'first_name': '' if user.is_superuser else user.first_name,
                          'last_name': '' if user.is_superuser else user.last_name})
        media = set()
        for obj in objects:
            for field in obj._meta.fields:
                if isinstance(field, FileField) and getattr(obj, field.name):
                    media.add(str(getattr(obj, field.name)))
        text = json.dumps(records, ensure_ascii=False)
        media.update(re.findall(r'/media/([^\s"<>]+)', text))
        output = Path(output)
        if output.exists():
            raise CommandError('Output exists; choose a new export filename.')
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('data.json', text)
            archive.writestr('users.json', json.dumps(users))
            archive.writestr('PRIVATE-NOTICE.txt',
                'Private licensing-review prototype. Not authorized for public redistribution.\n'
                'Story design: BootstrapMade. Preserve original attribution.\n')
            for relative in ('templates/story', 'static/themes/story'):
                for file in (root / relative).rglob('*'):
                    if file.is_file() and file.name != '.DS_Store':
                        archive.write(file, file.relative_to(root).as_posix())
            for name in media:
                file = (Path(settings.MEDIA_ROOT) / name).resolve()
                if not file.is_relative_to(Path(settings.MEDIA_ROOT).resolve()):
                    raise CommandError('Unsafe media path.')
                if not file.is_file():
                    raise CommandError(f'Referenced demo image missing: {name}')
                archive.write(file, 'media/' + name)
        self.stdout.write(f'Private export: {len(records)} records, {len(media)} media files.')
