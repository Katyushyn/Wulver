"""Install the private review bundle only into a newly initialized site."""
import json
from pathlib import Path
import zipfile
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.theme_manager.models import Theme
from apps.blog_manager.models import Article
from apps.userprofile.models import UserProfile
from apps.core_manager.models import SiteSettings
from wulver.paths import RESOURCES_DIR


class Command(BaseCommand):
    help = 'Install private Story demonstration. Not for public redistribution.'

    def handle(self, **options):
        bundle = RESOURCES_DIR / 'demo' / 'story.zip'
        if not bundle.is_file():
            raise CommandError('This clean distribution contains no private Story bundle.')
        if Theme.objects.exists() or Article.objects.exists():
            raise CommandError('Demo installation requires an empty site; no existing content will be overwritten.')
        User = get_user_model()
        administrator = User.objects.filter(is_superuser=True).first()
        if not administrator:
            raise CommandError('Create the administrator first.')
        created_files = []
        with zipfile.ZipFile(bundle) as archive:
            records = json.loads(archive.read('data.json'))
            users = json.loads(archive.read('users.json'))
            targets = []
            for entry in archive.infolist():
                if entry.is_dir() or not entry.filename.startswith(('templates/story/', 'static/themes/story/', 'media/')):
                    continue
                root = Path(settings.MEDIA_ROOT) if entry.filename.startswith('media/') else Path(settings.BASE_DIR)
                relative = entry.filename[6:] if entry.filename.startswith('media/') else entry.filename
                target = (root / relative).resolve()
                if not target.is_relative_to(root.resolve()) or target.exists():
                    raise CommandError(f'Unsafe or existing destination: {entry.filename}')
                targets.append((entry, target))
            try:
                with transaction.atomic():
                    user_map = {}
                    for source in users:
                        if source['administrator']:
                            user = administrator
                        else:
                            username = f"story-author-{source['source_id']}"
                            if User.objects.filter(username=username).exists():
                                raise CommandError('Demo author already exists.')
                            user = User.objects.create_user(username=username,
                                first_name=source['first_name'], last_name=source['last_name'])
                            user.set_unusable_password()
                            user.save(update_fields=['password'])
                        user_map[source['source_id']] = user.pk
                    for row in records:
                        model = apps.get_model(row['model'])
                        fields = row['fields']
                        for field in model._meta.get_fields():
                            if field.is_relation and field.related_model == User and field.name in fields:
                                value = fields[field.name]
                                fields[field.name] = [user_map[v] for v in value] if field.many_to_many else user_map.get(value)
                        if row['model'] == 'userprofile.userprofile':
                            profile, _ = UserProfile.objects.get_or_create(user_id=fields['user'])
                            row['pk'] = profile.pk
                        if row['model'] == 'django_comments.comment':
                            fields['content_type'] = ContentType.objects.get_for_model(Article).pk
                            fields['site'] = settings.SITE_ID
                    for obj in serializers.deserialize('json', json.dumps(records)):
                        obj.save()
                    for label in {row['model'] for row in records}:
                        expected_ids = [row['pk'] for row in records if row['model'] == label]
                        if apps.get_model(label).objects.filter(pk__in=expected_ids).count() != len(expected_ids):
                            raise CommandError(f'Incomplete demo import: {label}')
                    site = SiteSettings.get_solo()
                    if not site.home_page_id or not site.search_template_id:
                        raise CommandError('Demo homepage or search template is not configured.')
                    if not site.error_404_template_id:
                        from apps.theme_manager.models import ThemeTemplate, TemplateType
                        error = ThemeTemplate.objects.filter(theme__slug='story', template_type=TemplateType.ERROR_TEMPLATE).first()
                        if not error:
                            raise CommandError('Demo error template is missing.')
                        site.error_404_template = error
                        site.save(update_fields=['error_404_template'])
                    for template in apps.get_model('theme_manager.ThemeTemplate').objects.filter(theme__slug='story'):
                        if f'templates/story/{template.slug}.html' not in archive.namelist():
                            raise CommandError(f'Demo template file missing: {template.slug}')
                    for entry, target in targets:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        created_files.append(target)
                        with archive.open(entry) as source, target.open('xb') as destination:
                            import shutil
                            shutil.copyfileobj(source, destination)
                    notice = Path(settings.BASE_DIR) / 'PRIVATE-STORY-NOTICE.txt'
                    if not notice.exists():
                        notice.write_bytes(archive.read('PRIVATE-NOTICE.txt'))
                        created_files.append(notice)
            except Exception:
                for file in reversed(created_files):
                    file.unlink(missing_ok=True)
                raise
        self.stdout.write(self.style.SUCCESS('Private Story demo installed. Do not publicly redistribute before permission.'))
