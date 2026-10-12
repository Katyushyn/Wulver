import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.template import Context, Engine

from apps.theme_manager.admin import ThemeTemplateAdmin
from apps.theme_manager.models import (
    Theme,
    ThemeTemplate,
    ThemeTemplateVersion,
    TemplateType,
)
from apps.theme_manager.template_versions import save_template_code


class TemplateVersionTest(TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.base_dir = Path(self.temp_directory.name)
        self.settings_override = override_settings(BASE_DIR=self.base_dir)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.user = User.objects.create_superuser(
            username="version-admin",
            email="version@example.com",
            password="test",
        )
        self.theme = Theme.objects.create(
            name="Version Theme",
            slug="version-theme",
            is_active=True,
        )
        self.template = ThemeTemplate.objects.create(
            theme=self.theme,
            template_type=TemplateType.CHILDREN_PAGE,
            name="Home",
            slug="home",
            is_active=True,
        )
        self.file_path = (
            self.base_dir
            / "templates"
            / "version-theme"
            / "home.html"
        )
        self.file_path.parent.mkdir(parents=True)
        self.file_path.write_text("old line\nshared line\n", encoding="utf-8")
        self.admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
        self.factory = RequestFactory()

    def make_request(self, method, path="/", data=None):
        request = getattr(self.factory, method.lower())(path, data=data or {})
        request.user = self.user
        return request

    def test_save_creates_previous_version_and_skips_unchanged_code(self):
        changed = save_template_code(
            template=self.template,
            file_path=self.file_path,
            code="new line\nshared line\n",
            user=self.user,
            source="admin_save",
        )
        unchanged = save_template_code(
            template=self.template,
            file_path=self.file_path,
            code="new line\nshared line\n",
            user=self.user,
            source="admin_save",
        )

        self.assertTrue(changed)
        self.assertFalse(unchanged)
        self.assertEqual(self.template.versions.count(), 1)
        version = self.template.versions.get()
        self.assertEqual(version.code, "old line\nshared line\n")
        self.assertEqual(version.created_by, self.user)
        self.assertEqual(version.line_count, 2)

    def test_deleting_template_removes_file_and_version_history(self):
        version = ThemeTemplateVersion.objects.create(
            template=self.template,
            code="old line\n",
            code_hash="c" * 64,
            line_count=1,
            source="admin_save",
            created_by=self.user,
        )
        version_pk = version.pk

        self.template.delete()

        self.assertFalse(self.file_path.exists())
        self.assertFalse(ThemeTemplateVersion.objects.filter(pk=version_pk).exists())

    def test_history_and_compare_use_current_editor_code(self):
        version = ThemeTemplateVersion.objects.create(
            template=self.template,
            code="old line\nshared line\n",
            code_hash="a" * 64,
            line_count=2,
            source="admin_save",
            created_by=self.user,
        )

        history_response = self.admin.template_editor_history_view(
            self.make_request("get"),
            self.template.pk,
        )
        compare_response = self.admin.template_editor_history_compare_view(
            self.make_request(
                "post",
                data={
                    "version_id": version.pk,
                    "current_code": "new line\nshared line\nextra line\n",
                },
            ),
            self.template.pk,
        )

        history = json.loads(history_response.content)
        comparison = json.loads(compare_response.content)
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history["versions"][0]["id"], version.pk)
        self.assertEqual(comparison["added"], 2)
        self.assertEqual(comparison["removed"], 1)
        self.assertFalse(comparison["is_identical"])

    def test_restore_archives_current_code_before_replacing_file(self):
        version = ThemeTemplateVersion.objects.create(
            template=self.template,
            code="restored line\n",
            code_hash="b" * 64,
            line_count=1,
            source="admin_save",
            created_by=self.user,
        )
        self.file_path.write_text("current line\n", encoding="utf-8")

        response = self.admin.template_editor_history_restore_view(
            self.make_request(
                "post",
                data={
                    "version_id": version.pk,
                    "current_code": "unsaved editor line\n",
                },
            ),
            self.template.pk,
        )

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["changed"])
        self.assertEqual(
            self.file_path.read_text(encoding="utf-8"),
            "restored line\n",
        )
        self.assertTrue(
            self.template.versions.filter(code="current line\n").exists()
        )
        self.assertTrue(
            self.template.versions.filter(code="unsaved editor line\n").exists()
        )

    def test_save_clears_cached_template_loader(self):
        engine = Engine(
            dirs=[self.base_dir / "templates"],
            loaders=[
                (
                    "django.template.loaders.cached.Loader",
                    ["django.template.loaders.filesystem.Loader"],
                )
            ],
        )
        template_name = "version-theme/home.html"

        first_render = engine.get_template(template_name).render(Context({}))
        with patch(
            "apps.theme_manager.template_versions.engines.all",
            return_value=[SimpleNamespace(engine=engine)],
        ):
            save_template_code(
                template=self.template,
                file_path=self.file_path,
                code="fresh line\n",
                user=self.user,
                source="admin_save",
            )
        second_render = engine.get_template(template_name).render(Context({}))

        self.assertIn("old line", first_render)
        self.assertIn("fresh line", second_render)
        self.assertNotIn("old line", second_render)

    def test_save_model_renames_template_file_when_slug_changes(self):
        self.template.slug = "renamed-home"
        form = SimpleNamespace(
            cleaned_data={
                "template_html_code": "renamed line\nshared line\n",
            },
        )
        request = self.make_request(
            "post",
            data={
                "slug": "renamed-home",
            },
        )

        self.admin.save_model(
            request=request,
            obj=self.template,
            form=form,
            change=True,
        )

        renamed_file_path = (
            self.base_dir
            / "templates"
            / "version-theme"
            / "renamed-home.html"
        )
        self.assertFalse(self.file_path.exists())
        self.assertTrue(renamed_file_path.exists())
        self.assertEqual(
            renamed_file_path.read_text(encoding="utf-8"),
            "renamed line\nshared line\n",
        )
        self.assertTrue(
            self.template.versions.filter(
                code="old line\nshared line\n",
            ).exists()
        )
