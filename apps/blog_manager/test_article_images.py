from io import BytesIO
from pathlib import Path
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Article, ArticleImage, Category


def uploaded_image(name="content.png", size=(1800, 900), color="blue"):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type="image/png",
    )


class ArticleImageProcessingTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            title="News",
            slug="article-images-news",
            description="News",
            intro="News",
        )
        self.article = Article.objects.create(
            title="Article images",
            slug="article-images",
            description="Description",
            intro="Intro",
            body="Body",
            category=self.category,
        )

    def test_saves_only_resized_avif_without_crops_or_original(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                image = ArticleImage.objects.create(
                    article=self.article,
                    image=uploaded_image(),
                    alt_text="Content image",
                )

                self.assertTrue(image.image.name.endswith(".avif"))
                self.assertEqual((image.width, image.height), (1200, 600))
                files = list(Path(media_root).rglob("*.*"))
                self.assertEqual(len(files), 1)
                self.assertEqual(files[0].suffix, ".avif")
                self.assertNotIn("_crop", files[0].name)

                with Image.open(files[0]) as converted:
                    self.assertEqual(converted.format, "AVIF")
                    self.assertEqual(converted.size, (1200, 600))

                stored_path = files[0]
                image.delete()
                self.assertFalse(stored_path.exists())

    def test_keeps_smaller_image_dimensions(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                image = ArticleImage.objects.create(
                    article=self.article,
                    image=uploaded_image(size=(800, 1000)),
                )

                self.assertEqual((image.width, image.height), (800, 1000))


class ArticleImageAdminEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="article-image-admin",
            email="admin@example.com",
            password="password",
        )
        self.client.force_login(self.user)
        self.category = Category.objects.create(
            title="News",
            slug="article-image-endpoint-news",
            description="News",
            intro="News",
        )
        self.article = Article.objects.create(
            title="Article image endpoint",
            slug="article-image-endpoint",
            description="Description",
            intro="Intro",
            body="Body",
            category=self.category,
        )
        self.url = reverse(
            "admin:blog_manager_article_content_images",
            args=[self.article.pk],
        )

    def test_uploads_lists_updates_and_deletes_content_image(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    self.url,
                    {"action": "upload", "images": uploaded_image("My-photo.png")},
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(len(payload["images"]), 1)
                item = payload["images"][0]
                self.assertEqual(item["alt"], "My photo")
                self.assertTrue(item["url"].endswith(".avif"))
                self.assertEqual(item["width"], 1200)

                response = self.client.post(
                    self.url,
                    {
                        "action": "update",
                        "image_id": item["id"],
                        "alt": "Updated alt",
                        "sort_order": "3",
                    },
                )
                self.assertEqual(response.status_code, 200)
                updated = response.json()["images"][0]
                self.assertEqual(updated["alt"], "Updated alt")
                self.assertNotIn("caption", updated)
                self.assertEqual(updated["sort_order"], 3)

                stored_path = Path(media_root) / ArticleImage.objects.get().image.name
                response = self.client.post(
                    self.url,
                    {"action": "delete", "image_id": item["id"]},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["images"], [])
                self.assertFalse(stored_path.exists())
