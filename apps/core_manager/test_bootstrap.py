from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from apps.blog_manager.models import Article
from apps.theme_manager.models import Theme, ThemeTemplate
from .models import SiteSettings


class CleanBootstrapTests(TestCase):
    def test_minimal_site_without_demo_and_refusal_to_overwrite(self):
        with TemporaryDirectory() as directory, override_settings(BASE_DIR=Path(directory)):
            call_command('wulver_bootstrap', verbosity=0)
            site = SiteSettings.get_solo()
            self.assertEqual(Article.objects.count(), 0)
            self.assertEqual(Theme.objects.count(), 1)
            self.assertEqual(ThemeTemplate.objects.count(), 3)
            self.assertEqual(site.home_page.slug, 'home')
            self.assertTrue((Path(directory) / 'templates/wulver-system/home.html').exists())
            with self.assertRaises(CommandError):
                call_command('wulver_bootstrap', verbosity=0)
            self.assertEqual(ThemeTemplate.objects.count(), 3)
