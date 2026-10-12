from pathlib import Path
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from unittest.mock import patch
import hashlib
from .environment_dashboard import update_environment, env_values, BOOLEAN_FIELDS


class EnvironmentDashboardTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(BASE_DIR=Path(self.directory.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.path = Path(self.directory.name) / '.env'
        self.path.write_text('# preserve me\nDEBUG=True\nOPENAI_API_KEY=private-test-token\n')
        self.user = get_user_model().objects.create_superuser('environment-admin', password='test-password')
        self.client.force_login(self.user)

    def test_secret_is_not_rendered(self):
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OPENAI_API_KEY')
        self.assertNotContains(response, 'private-test-token')

    def test_email_backend_has_select_and_help(self):
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'id="env-email-backend"')
        self.assertContains(response, 'Console — local development')
        self.assertContains(response, 'SMTP — send real email')
        self.assertNotContains(response, 'name="clear_EMAIL_BACKEND"')

    def test_reload_probe_and_overlay(self):
        response = self.client.get(reverse('admin:index'), {'environment_probe': '1'})
        self.assertTrue(response.json()['process'])
        response = self.client.get(reverse('admin:index'), {'environment_reload': '1'})
        self.assertContains(response, 'id="wulver-reload-overlay"')
        self.assertContains(response, 'waitForServer()')

    def test_activity_panels_are_limited_and_environment_collapsed(self):
        from .models import ContactMessage
        for number in range(7):
            ContactMessage.objects.create(name='Demo', email='demo@example.com', subject=f'Message {number}', message='Body')
        response = self.client.get(reverse('admin:index'))
        panels = response.context['activity_panels']
        self.assertEqual(len(panels), 6)
        panel = next(p for p in panels if str(p['title']) == 'Contact messages')
        self.assertNotIn('records', panel)
        self.assertEqual(panel['count'], 7)
        self.assertEqual(panel['attention_count'], 7)
        self.assertEqual(response.context['title'], 'Site overview')
        self.assertNotContains(response, 'height:240px')
        self.assertContains(response, '<details class=')
        self.assertNotContains(response, '<details open')

    def test_review_keeps_new_records_unseen(self):
        from .models import NewsletterSubscription
        NewsletterSubscription.objects.create(email='first@example.com')
        response = self.client.get(reverse('admin:index'))
        panel = next(p for p in response.context['activity_panels'] if 'newslettersubscription' in p['url'])
        token = panel['seen_token']
        NewsletterSubscription.objects.create(email='second@example.com')
        self.assertEqual(self.client.post(reverse('admin:index'), {'environment_action': 'mark_seen', 'seen_token': token}).status_code, 302)
        response = self.client.get(reverse('admin:index'))
        panel = next(p for p in response.context['activity_panels'] if 'newslettersubscription' in p['url'])
        self.assertEqual(panel['attention_count'], 1)
        other = get_user_model().objects.create_superuser('other-admin', password='test-password')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('admin:index'), {'environment_action': 'mark_seen', 'seen_token': token}).status_code, 403)

    def test_overview_version_and_backup_status(self):
        from apps.backup_manager.models import BackupSnapshot
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'No backups yet.')
        self.assertContains(response, 'Open site')
        self.assertTrue(response.context['wulver_version'])
        snapshot = BackupSnapshot.objects.create(status='failed')
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.context['overview_backups']['latest'], snapshot)
        self.assertContains(response, 'No completed backup is available.')

    def test_save_and_clear_preserve_other_settings(self):
        response = self.client.post(reverse('admin:index'), {
            'environment_key': 'OPENAI_API_KEY', 'environment_action': 'save',
            'environment_value': 'replacement-private-token',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(env_values(self.path.read_text())['OPENAI_API_KEY'], 'replacement-private-token')
        self.client.post(reverse('admin:index'), {'environment_key': 'OPENAI_API_KEY', 'environment_action': 'clear'})
        self.assertEqual(env_values(self.path.read_text())['OPENAI_API_KEY'], '')
        self.assertIn('# preserve me', self.path.read_text())
        self.assertEqual(env_values(self.path.read_text())['DEBUG'], 'True')

    def test_staff_cannot_write(self):
        self.user.is_superuser = False
        self.user.save(update_fields=['is_superuser'])
        response = self.client.post(reverse('admin:index'), {
            'environment_key': 'OPENAI_API_KEY', 'environment_action': 'clear',
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(env_values(self.path.read_text())['OPENAI_API_KEY'], 'private-test-token')

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('admin:index'), {
            'environment_key': 'OPENAI_API_KEY', 'environment_action': 'clear',
        }).status_code, 403)

    def test_injection_and_secret_key_removal_rejected(self):
        for key, value in [('PYTHONPATH', 'unsafe'), ('OPENAI_API_KEY', 'x\nDEBUG=False'), ('SECRET_KEY', '')]:
            with self.assertRaises(ValidationError):
                update_environment(self.path, key, value)

    def test_quoted_value_and_duplicate_reset(self):
        self.path.write_text('OPENAI_API_KEY=old\nOPENAI_API_KEY=duplicate\n')
        update_environment(self.path, 'OPENAI_API_KEY', 'quoted # value " and \\')
        self.assertEqual(env_values(self.path.read_text())['OPENAI_API_KEY'], 'quoted # value " and \\')
        self.assertEqual(self.path.read_text().count('OPENAI_API_KEY='), 1)

    def apply_payload(self):
        payload = {'environment_action': 'apply', 'confirm_risks': 'on',
                   'environment_revision': hashlib.sha256(self.path.read_text().encode()).hexdigest(),
                   'ALLOWED_HOSTS': 'testserver', 'SECURE_HSTS_SECONDS': '0',
                   'CSRF_TRUSTED_ORIGINS': '', 'ACCOUNT_DEFAULT_HTTP_PROTOCOL': 'http'}
        for key in ('DEBUG', 'SERVE_MEDIA_LOCALLY', 'EMAIL_USE_TLS', 'CSP_ENABLED'):
            payload['switch_' + key] = 'on'
        return payload

    @patch('apps.core_manager.environment_runtime.request_restart', return_value='manual')
    def test_batch_apply(self, restart):
        payload = self.apply_payload()
        payload['value_GITHUB_TOKEN'] = 'new-private-github-token'
        payload['clear_OPENAI_API_KEY'] = 'on'
        self.assertEqual(self.client.post(reverse('admin:index'), payload).status_code, 302)
        values = env_values(self.path.read_text())
        self.assertEqual(values['GITHUB_TOKEN'], 'new-private-github-token')
        self.assertEqual(values['OPENAI_API_KEY'], '')
        self.assertEqual(values['DEBUG'], 'True')
        restart.assert_called_once()

    @patch('apps.core_manager.environment_runtime.request_restart')
    def test_http_secure_cookies_blocked_without_partial_write(self, restart):
        before = self.path.read_text()
        payload = self.apply_payload()
        payload['switch_SESSION_COOKIE_SECURE'] = 'on'
        self.client.post(reverse('admin:index'), payload)
        self.assertEqual(self.path.read_text(), before)
        restart.assert_not_called()

    @patch('apps.core_manager.environment_runtime.request_restart')
    def test_stale_form_blocked(self, restart):
        payload = self.apply_payload()
        self.path.write_text(self.path.read_text() + '# another editor\n')
        before = self.path.read_text()
        self.client.post(reverse('admin:index'), payload)
        self.assertEqual(self.path.read_text(), before)
        restart.assert_not_called()

    @patch('apps.core_manager.environment_runtime.request_restart')
    def test_confirmation_required(self, restart):
        payload = self.apply_payload()
        payload.pop('confirm_risks')
        before = self.path.read_text()
        self.client.post(reverse('admin:index'), payload)
        self.assertEqual(self.path.read_text(), before)
        restart.assert_not_called()
