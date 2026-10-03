import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.backup_manager.forms import CreateBackupForm, RestoreBackupForm, VerifyBackupForm
from apps.backup_manager.models import BackupSettings, BackupSnapshot
from apps.backup_manager.services.archive import (
    ARCHIVE_FORMAT,
    BackupArchiveError,
    create_backup_archive,
    import_backup_archive,
    restore_backup_archive,
    verify_backup_archive,
)
from apps.backup_manager.services.database import (
    MicrosoftSQLServerAdapter,
    MySQLAdapter,
    PostgreSQLAdapter,
)
from apps.backup_manager.services.paths import BackupPathError, BackupRoot, collect_backup_roots


class FakeDatabaseAdapter:
    adapter_name = "fake"
    extension = ".dump"
    vendor = "fake-db"

    def create_dump(self, destination):
        Path(destination).write_bytes(b"portable database dump")

    def restore_dump(self, source, manifest):
        self.restored_dump = Path(source).read_bytes()

    def manifest(self, dump_name):
        return {
            "alias": "default",
            "vendor": self.vendor,
            "adapter": self.adapter_name,
            "format": "test-dump",
            "dump_file": dump_name,
            "database_name": "test",
        }


class BackupSettingsTests(TestCase):
    def test_singleton_and_absolute_path_validation(self):
        first = BackupSettings.get_solo()
        second = BackupSettings.get_solo()
        self.assertEqual(first.pk, 1)
        self.assertEqual(first.pk, second.pk)

        first.backup_directory = "relative/backups"
        with self.assertRaises(ValidationError):
            first.save()

    def test_nested_static_and_media_roots_are_not_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            static_root = project / "staticfiles"
            media_root = project / "media"
            static_root.mkdir(parents=True)
            media_root.mkdir()
            configuration = BackupSettings.get_solo()
            configuration.backup_directory = str(Path(directory) / "backups")
            configuration.save()
            with override_settings(
                BASE_DIR=project,
                STATIC_ROOT=static_root,
                MEDIA_ROOT=media_root,
                TEMPLATES=[],
            ):
                roots = collect_backup_roots(configuration)
            self.assertEqual([(root.name, root.path) for root in roots], [("project", project.resolve())])

    def test_backup_directory_cannot_be_inside_project(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            configuration = BackupSettings.get_solo()
            configuration.backup_directory = str(project / "backups")
            configuration.save()
            with override_settings(BASE_DIR=project, STATIC_ROOT=None, MEDIA_ROOT=None, TEMPLATES=[]):
                with self.assertRaises(BackupPathError):
                    collect_backup_roots(configuration)


class BackupFormTests(TestCase):
    def test_backup_password_is_required_and_confirmed(self):
        form = CreateBackupForm(
            {"description": "Before release", "password": "long-password", "password_confirm": "different"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("password_confirm", form.errors)

    def test_restore_requires_exactly_one_source(self):
        form = RestoreBackupForm({"password": "long-password", "confirmation": "on"})
        self.assertFalse(form.is_valid())
        self.assertIn("Choose one saved backup", str(form.non_field_errors()))

    def test_restore_upload_uses_bordered_unfold_file_widget(self):
        html = str(RestoreBackupForm()["uploaded_backup"])

        self.assertIn("border-base-200", html)
        self.assertIn("focus-within:outline-primary-600", html)
        self.assertIn('accept=".zip,application/zip"', html)
        self.assertIn("file_upload", html)

    def test_backup_forms_use_visible_unfold_widgets(self):
        bordered_fields = (
            (CreateBackupForm(), ("description", "password", "password_confirm")),
            (RestoreBackupForm(), ("snapshot", "description", "password")),
            (VerifyBackupForm(), ("password",)),
        )

        for form, field_names in bordered_fields:
            for field_name in field_names:
                with self.subTest(form=form.__class__.__name__, field=field_name):
                    self.assertIn("border-base-200", str(form[field_name]))

        self.assertIn("rounded-full", str(RestoreBackupForm()["confirmation"]))


class BackupAdminAppearanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="backup-admin",
            email="backup@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_backup_actions_use_standard_admin_action_button_style(self):
        response = self.client.get(
            reverse("admin:backup_manager_backupsnapshot_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-admin-action="restore-backup"')
        self.assertContains(response, 'data-admin-action="create-full-backup"')
        self.assertContains(response, "settings_backup_restore")
        self.assertContains(response, "dark:hover:text-primary-500")


class BackupArchiveTests(TestCase):
    password = "strong-test-password"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "empty").mkdir()
        (self.project / "hello.txt").write_text("original", encoding="utf-8")
        self.backup_root = self.root / "backups"
        configuration = BackupSettings.get_solo()
        configuration.backup_directory = str(self.backup_root)
        configuration.additional_paths = ""
        configuration.compression_level = 1
        configuration.save()
        self.adapter = FakeDatabaseAdapter()

    def create_snapshot(self):
        snapshot = BackupSnapshot.objects.create(description="Test backup")
        with (
            patch(
                "apps.backup_manager.services.archive.collect_backup_roots",
                return_value=(BackupRoot("project", self.project, "project"),),
            ),
            patch(
                "apps.backup_manager.services.archive.current_restore_targets",
                return_value={"project": self.project},
            ),
            patch(
                "apps.backup_manager.services.archive.get_database_adapter",
                return_value=self.adapter,
            ),
        ):
            create_backup_archive(snapshot, self.password)
        snapshot.refresh_from_db()
        return snapshot

    def test_encrypted_archive_verification_and_wrong_password(self):
        snapshot = self.create_snapshot()
        manifest = verify_backup_archive(snapshot, self.password)
        self.assertEqual(manifest["format"], ARCHIVE_FORMAT)
        self.assertEqual(snapshot.status, BackupSnapshot.Status.COMPLETED)
        with self.assertRaises(BackupArchiveError):
            verify_backup_archive(snapshot, "wrong-password", full=False)

    def test_deleting_record_deletes_zip(self):
        snapshot = self.create_snapshot()
        archive = snapshot.archive_file
        self.assertTrue(archive.exists())
        snapshot.delete()
        self.assertFalse(archive.exists())

    def test_uploaded_backup_is_copied_and_registered(self):
        original = self.create_snapshot()
        with original.archive_file.open("rb") as source:
            from django.core.files.uploadedfile import SimpleUploadedFile

            uploaded = SimpleUploadedFile("local.zip", source.read(), content_type="application/zip")
        imported = import_backup_archive(uploaded, self.password, description="Imported")
        self.assertEqual(imported.source, BackupSnapshot.Source.UPLOADED)
        self.assertTrue(imported.archive_exists)
        self.assertNotEqual(imported.archive_path, original.archive_path)

    def test_restore_replaces_project_and_uses_manifest_database_adapter(self):
        snapshot = self.create_snapshot()
        (self.project / "hello.txt").write_text("changed", encoding="utf-8")
        (self.project / "obsolete.txt").write_text("remove me", encoding="utf-8")
        with (
            override_settings(BASE_DIR=self.project),
            patch(
                "apps.backup_manager.services.archive.current_restore_targets",
                return_value={"project": self.project},
            ),
            patch(
                "apps.backup_manager.services.archive.get_database_adapter",
                return_value=self.adapter,
            ) as adapter_factory,
        ):
            restore_backup_archive(snapshot, self.password)
        self.assertEqual((self.project / "hello.txt").read_text(encoding="utf-8"), "original")
        self.assertFalse((self.project / "obsolete.txt").exists())
        self.assertTrue((self.project / "empty").is_dir())
        self.assertEqual(self.adapter.restored_dump, b"portable database dump")
        adapter_factory.assert_called_with("default", expected_adapter="fake")


class NativeDatabaseAdapterTests(TestCase):
    def _adapter(self, cls, config):
        adapter = cls.__new__(cls)
        adapter.alias = "default"
        adapter.connection = MagicMock()
        adapter.config = config
        return adapter

    @patch("apps.backup_manager.services.database._run")
    @patch("apps.backup_manager.services.database._required_executable", return_value="/usr/bin/pg_dump")
    def test_postgresql_dump_uses_native_custom_format_without_password_argument(self, _executable, run):
        adapter = self._adapter(
            PostgreSQLAdapter,
            {"NAME": "wulver", "USER": "cms", "PASSWORD": "secret", "HOST": "db", "PORT": "5432"},
        )
        adapter.create_dump("backup.pgdump")
        command = run.call_args.args[0]
        self.assertIn("--format=custom", command)
        self.assertNotIn("secret", command)
        self.assertEqual(run.call_args.kwargs["env"]["PGPASSWORD"], "secret")

    @patch("apps.backup_manager.services.database._run")
    @patch("apps.backup_manager.services.database._required_executable", return_value="/usr/bin/mariadb-dump")
    def test_mysql_dump_includes_complete_database_and_uses_environment_password(self, _executable, run):
        adapter = self._adapter(
            MySQLAdapter,
            {"NAME": "wulver", "USER": "cms", "PASSWORD": "secret", "HOST": "db", "PORT": "3306"},
        )
        with tempfile.NamedTemporaryFile() as destination:
            adapter.create_dump(destination.name)
        command = run.call_args.args[0]
        self.assertIn("--add-drop-database", command)
        self.assertIn("--databases", command)
        self.assertNotIn("secret", command)
        self.assertEqual(run.call_args.kwargs["env"]["MYSQL_PWD"], "secret")

    @patch("apps.backup_manager.services.database._run")
    @patch("apps.backup_manager.services.database._required_executable", return_value="sqlpackage")
    def test_mssql_dump_uses_bacpac_export(self, _executable, run):
        adapter = self._adapter(
            MicrosoftSQLServerAdapter,
            {"NAME": "wulver", "USER": "cms", "PASSWORD": "secret", "HOST": "db", "PORT": "1433"},
        )
        adapter.create_dump("backup.bacpac")
        command = run.call_args.args[0]
        self.assertIn("/Action:Export", command)
        self.assertIn("/TargetFile:backup.bacpac", command)


class BackupAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="backup-admin", email="backup@example.com", password="password"
        )
        self.client.force_login(self.user)

    def test_backup_admin_pages_render(self):
        for url in (
            reverse("admin:backup_manager_backupsnapshot_changelist"),
            reverse("admin:backup_manager_backupsnapshot_create_full"),
            reverse("admin:backup_manager_backupsnapshot_restore"),
            reverse("admin:backup_manager_backupsettings_changelist"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
                self.assertEqual(response.status_code, 200)

    @patch("apps.backup_manager.admin.spawn_backup_job")
    def test_create_view_registers_background_job_without_storing_password(self, spawn):
        response = self.client.post(
            reverse("admin:backup_manager_backupsnapshot_create_full"),
            {
                "description": "Before deployment",
                "password": "strong-password",
                "password_confirm": "strong-password",
            },
        )
        self.assertRedirects(response, reverse("admin:backup_manager_backupsnapshot_changelist"))
        snapshot = BackupSnapshot.objects.get(description="Before deployment")
        spawn.assert_called_once_with("create_full_backup", snapshot.pk, "strong-password")
        self.assertNotIn("password", snapshot.manifest)
