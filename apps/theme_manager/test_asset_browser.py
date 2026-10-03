import json
import tempfile
from pathlib import Path

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import AnonymousUser, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from apps.theme_manager.admin import ThemeTemplateAdmin
from apps.theme_manager.asset_browser import (
    AssetUploadError,
    collect_image_assets,
    delete_image_assets,
    save_uploaded_image,
)
from apps.theme_manager.models import ThemeTemplate


class AssetBrowserTest(TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.root = Path(self.temp_directory.name)
        self.static_root = self.root / "static"
        self.media_root = self.root / "media"
        (self.static_root / "themes" / "demo").mkdir(parents=True)
        (self.media_root / "uploads").mkdir(parents=True)
        (self.static_root / "themes" / "demo" / "hero.jpg").write_bytes(b"jpg")
        (self.static_root / "themes" / "demo" / "readme.txt").write_text(
            "ignore",
            encoding="utf-8",
        )
        (self.media_root / "uploads" / "photo.avif").write_bytes(b"avif")
        self.settings_override = override_settings(
            STATICFILES_DIRS=[self.static_root],
            MEDIA_ROOT=self.media_root,
            STATIC_URL="/static/",
            MEDIA_URL="/media/",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.factory = RequestFactory()
        self.admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
        self.user = User.objects.create_superuser(
            username="asset-admin",
            email="asset@example.com",
            password="test",
        )

    def test_collects_static_and_media_images_with_insert_values(self):
        assets = collect_image_assets()

        self.assertEqual(len(assets), 2)
        static_asset = next(item for item in assets if item["type"] == "static")
        media_asset = next(item for item in assets if item["type"] == "media")
        self.assertEqual(static_asset["path"], "themes/demo/hero.jpg")
        self.assertEqual(
            static_asset["insert_value"],
            "{% static 'themes/demo/hero.jpg' %}",
        )
        self.assertEqual(static_asset["preview_url"], "/static/themes/demo/hero.jpg")
        self.assertEqual(media_asset["path"], "uploads/photo.avif")
        self.assertEqual(media_asset["insert_value"], "/media/uploads/photo.avif")
        self.assertEqual(media_asset["preview_url"], "/media/uploads/photo.avif")

    def test_endpoint_returns_counts_and_requires_permission(self):
        request = self.factory.get("/")
        request.user = self.user
        response = self.admin.template_editor_asset_browser_view(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["static_count"], 1)
        self.assertEqual(payload["media_count"], 1)

        anonymous_request = self.factory.get("/")
        anonymous_request.user = AnonymousUser()
        denied = self.admin.template_editor_asset_browser_view(anonymous_request)
        self.assertEqual(denied.status_code, 403)

    def test_uploads_new_static_image_and_returns_asset(self):
        upload = SimpleUploadedFile(
            "banner.png",
            b"new png bytes",
            content_type="image/png",
        )

        asset, replaced = save_uploaded_image(
            upload,
            "static",
            "themes/demo/banner.png",
        )

        self.assertFalse(replaced)
        self.assertEqual(asset["path"], "themes/demo/banner.png")
        self.assertEqual(asset["type"], "static")
        self.assertEqual(
            (self.static_root / "themes" / "demo" / "banner.png").read_bytes(),
            b"new png bytes",
        )

    def test_requires_confirmation_before_replacing_existing_image(self):
        target = self.static_root / "themes" / "demo" / "hero.jpg"
        upload = SimpleUploadedFile("hero.jpg", b"replacement")

        with self.assertRaisesMessage(AssetUploadError, "Confirm replacement"):
            save_uploaded_image(
                upload,
                "static",
                "themes/demo/hero.jpg",
            )

        asset, replaced = save_uploaded_image(
            upload,
            "static",
            "themes/demo/hero.jpg",
            overwrite=True,
        )
        self.assertTrue(replaced)
        self.assertEqual(asset["path"], "themes/demo/hero.jpg")
        self.assertEqual(target.read_bytes(), b"replacement")

    def test_rejects_unsafe_paths_and_mismatched_extensions(self):
        with self.assertRaises(AssetUploadError):
            save_uploaded_image(
                SimpleUploadedFile("photo.png", b"png"),
                "media",
                "../photo.png",
            )
        with self.assertRaisesMessage(AssetUploadError, "extension must match"):
            save_uploaded_image(
                SimpleUploadedFile("photo.png", b"png"),
                "media",
                "uploads/photo.jpg",
            )

    def test_post_endpoint_replaces_selected_image(self):
        request = self.factory.post(
            "/",
            {
                "asset_type": "static",
                "path": "themes/demo/hero.jpg",
                "overwrite": "true",
                "image": SimpleUploadedFile("hero.jpg", b"endpoint replacement"),
            },
        )
        request.user = self.user

        response = self.admin.template_editor_asset_browser_view(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["replaced"])
        self.assertEqual(payload["asset"]["path"], "themes/demo/hero.jpg")

    def test_deletes_multiple_images_from_disk(self):
        media_file = self.media_root / "uploads" / "photo.avif"
        static_file = self.static_root / "themes" / "demo" / "hero.jpg"

        deleted, failed = delete_image_assets([
            {"type": "media", "path": "uploads/photo.avif"},
            {"type": "static", "path": "themes/demo/hero.jpg"},
        ])

        self.assertEqual(failed, [])
        self.assertEqual(
            deleted,
            [
                {"type": "media", "path": "uploads/photo.avif"},
                {"type": "static", "path": "themes/demo/hero.jpg"},
            ],
        )
        self.assertFalse(media_file.exists())
        self.assertFalse(static_file.exists())

    def test_delete_reports_failed_items_without_stopping_batch(self):
        media_file = self.media_root / "uploads" / "photo.avif"

        deleted, failed = delete_image_assets([
            {"type": "media", "path": "../photo.avif"},
            {"type": "media", "path": "uploads/photo.avif"},
            {"type": "media", "path": "uploads/missing.avif"},
        ])

        self.assertEqual(deleted, [{"type": "media", "path": "uploads/photo.avif"}])
        self.assertEqual(len(failed), 2)
        self.assertIn("valid relative image path", failed[0]["error"])
        self.assertIn("not found", failed[1]["error"])
        self.assertFalse(media_file.exists())

    def test_post_endpoint_deletes_selected_images(self):
        request = self.factory.post(
            "/",
            {
                "action": "delete_many",
                "assets": json.dumps([
                    {"type": "media", "path": "uploads/photo.avif"},
                    {"type": "static", "path": "themes/demo/hero.jpg"},
                ]),
            },
        )
        request.user = self.user

        response = self.admin.template_editor_asset_browser_view(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["deleted"]), 2)
        self.assertEqual(payload["failed"], [])
        self.assertFalse((self.media_root / "uploads" / "photo.avif").exists())
        self.assertFalse((self.static_root / "themes" / "demo" / "hero.jpg").exists())

    def test_post_endpoint_treats_assets_payload_as_delete(self):
        request = self.factory.post(
            "/",
            {
                "assets": json.dumps([
                    {"type": "media", "path": "uploads/photo.avif"},
                ]),
            },
        )
        request.user = self.user

        response = self.admin.template_editor_asset_browser_view(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            payload["deleted"],
            [{"type": "media", "path": "uploads/photo.avif"}],
        )
        self.assertFalse((self.media_root / "uploads" / "photo.avif").exists())
