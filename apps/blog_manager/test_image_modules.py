from io import BytesIO
from pathlib import Path
import tempfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.template import Context, Template
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .image_module_storage import (
    DESKTOP_CROP_SIZE,
    MAX_FILES_PER_MODULE,
    MOBILE_CROP_SIZE,
    delete_manifest_files,
    delete_module_storage,
    manifest_with_urls,
    store_image_uploads,
    validate_image_uploads,
)
from .models import ImageModule


def make_uploaded_image(name="example.png", size=(800, 600), color="blue"):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


class ImageModuleStorageTests(TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_directory.name)
        self.settings_override.enable()
        self.module = ImageModule.objects.create(
            name="Gallery",
            slug="test-image-gallery",
        )

    def tearDown(self):
        self.settings_override.disable()
        self.temp_directory.cleanup()

    def test_upload_is_converted_to_avif_and_added_to_module_folder(self):
        upload = make_uploaded_image()
        validate_image_uploads([upload], [])
        entries = store_image_uploads(self.module, [upload])

        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]["file"].startswith(f"{self.module.storage_prefix}/"))
        self.assertTrue(entries[0]["file"].endswith(".avif"))
        self.assertTrue(entries[0]["crop_file"].endswith("_crop.avif"))
        self.assertTrue(entries[0]["crop_mob_file"].endswith("_crop_mob.avif"))
        self.assertEqual(entries[0]["alt"], "example")
        self.assertGreater(entries[0]["size"], 0)

        with default_storage.open(entries[0]["crop_file"], "rb") as image_file:
            with Image.open(image_file) as image:
                self.assertEqual(image.size, DESKTOP_CROP_SIZE)
        with default_storage.open(entries[0]["crop_mob_file"], "rb") as image_file:
            with Image.open(image_file) as image:
                self.assertEqual(image.size, MOBILE_CROP_SIZE)

        urls = manifest_with_urls(entries)
        self.assertTrue(urls[0]["crop_url"].endswith("_crop.avif"))
        self.assertTrue(urls[0]["crop_mob_url"].endswith("_crop_mob.avif"))

        delete_manifest_files(self.module, entries)
        for field_name in ("file", "crop_file", "crop_mob_file"):
            self.assertFalse(default_storage.exists(entries[0][field_name]))

    def test_module_file_limit_is_validated(self):
        existing = [
            {"id": str(index), "size": 1}
            for index in range(MAX_FILES_PER_MODULE)
        ]

        with self.assertRaises(ValidationError):
            validate_image_uploads([make_uploaded_image()], existing)

    def test_deleting_module_storage_removes_entire_folder_and_orphan_files(self):
        entries = store_image_uploads(self.module, [make_uploaded_image()])
        orphan_path = default_storage.save(
            f"{self.module.storage_prefix}/orphan.avif",
            ContentFile(b"orphan"),
        )
        module_directory = Path(default_storage.path(self.module.storage_prefix))

        self.assertTrue(module_directory.is_dir())
        self.assertTrue(default_storage.exists(orphan_path))
        self.assertTrue(default_storage.exists(entries[0]["file"]))

        delete_module_storage(self.module)

        self.assertFalse(module_directory.exists())
        self.assertFalse(default_storage.exists(orphan_path))
        self.assertFalse(default_storage.exists(entries[0]["file"]))


class ImageModuleTemplateTagTests(TestCase):
    def test_ordered_count_returns_active_items_in_manifest_order(self):
        module = ImageModule.objects.create(
            name="Ordered",
            slug="test-image-ordered",
            display_mode=ImageModule.DisplayMode.ORDERED_COUNT,
            images_count=2,
            manifest=[
                {"id": "1", "file": "image_modules/one.avif", "alt": "One", "active": True},
                {"id": "2", "file": "image_modules/two.avif", "alt": "Two", "active": False},
                {"id": "3", "file": "image_modules/three.avif", "alt": "Three", "active": True},
            ],
        )

        rendered = Template(
            "{% load image_modules %}"
            "{% image_module 'test-image-ordered' as images %}"
            "{% for image in images %}{{ image.alt }},{% endfor %}"
        ).render(Context())

        self.assertEqual(rendered, "One,Three,")

    def test_inactive_or_unknown_module_returns_no_images(self):
        ImageModule.objects.create(
            name="Inactive",
            slug="test-image-inactive",
            is_active=False,
        )

        rendered = Template(
            "{% load image_modules %}"
            "{% image_module 'test-image-inactive' as images %}"
            "{{ images|length }}"
        ).render(Context())

        self.assertEqual(rendered, "0")


class ImageModuleAdminTests(TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_directory.name)
        self.settings_override.enable()
        self.user = User.objects.create_superuser(
            username="image-admin",
            email="image-admin@example.com",
            password="test",
        )
        self.client.force_login(self.user)

    def tearDown(self):
        self.settings_override.disable()
        self.temp_directory.cleanup()

    def test_info_dialog_is_available_on_list_and_change_pages(self):
        module = ImageModule.objects.create(
            name="Info gallery",
            slug="info-gallery",
        )

        list_response = self.client.get(
            reverse("admin:blog_manager_imagemodule_changelist")
        )
        change_response = self.client.get(
            reverse("admin:blog_manager_imagemodule_change", args=[module.pk])
        )

        for response in (list_response, change_response):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "data-admin-help-open")
            self.assertContains(response, "data-admin-help-dialog")
            self.assertContains(response, "Modules — Images")
            self.assertContains(response, "600×400 desktop")
            self.assertContains(response, "380×253 mobile")

        history_url = reverse(
            "admin:blog_manager_imagemodule_history",
            args=[module.pk],
        )
        content = change_response.content.decode()
        self.assertLess(
            content.index("data-admin-help-open"),
            content.index(history_url),
        )

    def test_admin_uploads_multiple_image_field_and_builds_manifest(self):
        response = self.client.post(
            reverse("admin:blog_manager_imagemodule_add"),
            {
                "name": "Admin gallery",
                "slug": "test-admin-gallery",
                "display_mode": ImageModule.DisplayMode.RANDOM_ONE,
                "images_count": 1,
                "is_active": "on",
                "manifest_editor": "[]",
                "uploads": [
                    make_uploaded_image("first.png", color="red"),
                    make_uploaded_image("second.png", color="green"),
                ],
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        module = ImageModule.objects.get(slug="test-admin-gallery")
        self.assertEqual(len(module.manifest), 2)
        self.assertEqual(
            {item["alt"] for item in module.manifest},
            {"first", "second"},
        )

        change_response = self.client.get(
            reverse("admin:blog_manager_imagemodule_change", args=[module.pk])
        )
        self.assertEqual(change_response.status_code, 200)
        self.assertContains(change_response, "image-module-gallery")
        self.assertContains(change_response, "id_manifest_editor")
