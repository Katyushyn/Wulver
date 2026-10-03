import base64
import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pillow_avif  # noqa: F401
from PIL import Image
from django.contrib.admin.sites import AdminSite
from django.test import TestCase, override_settings

from apps.theme_manager.admin import ThemeTemplateAdmin
from apps.theme_manager.ai_image_generator import parse_selected_image
from apps.theme_manager.models import Theme, ThemeTemplate, TemplateType


def make_png(size, color):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


class SelectedImageParsingTest(TestCase):
    def test_parses_static_tag_inside_img_tag(self):
        selected = (
            '<img class="hero" '
            'src="{% static \'themes/eterna/assets/img/hero.jpg\' %}" alt="">'
        )

        result = parse_selected_image(selected)

        self.assertEqual(
            result.source_path,
            "themes/eterna/assets/img/hero.jpg",
        )
        self.assertEqual(
            result.replace_source("/media/ai-images/new.avif"),
            '<img class="hero" src="/media/ai-images/new.avif" alt="">',
        )

    def test_parses_selected_static_tag(self):
        result = parse_selected_image(
            "{% static 'themes/eterna/assets/img/hero.jpg' %}"
        )

        self.assertEqual(
            result.source_path,
            "themes/eterna/assets/img/hero.jpg",
        )
        self.assertEqual(
            result.replace_source("/media/ai-images/new.avif"),
            "/media/ai-images/new.avif",
        )

    def test_preserves_whitespace_around_selected_path(self):
        result = parse_selected_image(
            "\n  {% static 'themes/eterna/assets/img/hero.jpg' %}  \n"
        )

        self.assertEqual(
            result.replace_source("/media/ai-images/new.avif"),
            "\n  /media/ai-images/new.avif  \n",
        )


class ImageGenerationTest(TestCase):
    def test_selected_static_tag_is_replaced_with_plain_media_url(self):
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            static_path = (
                base_dir
                / "static"
                / "themes"
                / "eterna"
                / "assets"
                / "img"
                / "hero.jpg"
            )
            static_path.parent.mkdir(parents=True)
            Image.new("RGB", (320, 180), "blue").save(static_path, format="JPEG")

            theme = Theme.objects.create(
                name="Eterna",
                slug="eterna",
                is_active=True,
            )
            template = ThemeTemplate.objects.create(
                theme=theme,
                name="Home",
                slug="home",
                template_type=TemplateType.PARENT_PAGE,
                is_active=True,
            )
            ai_response = SimpleNamespace(data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(
                        make_png((1024, 1024), "green")
                    ).decode("ascii")
                )
            ])

            with override_settings(
                BASE_DIR=base_dir,
                MEDIA_ROOT=base_dir / "media",
                STATICFILES_DIRS=[base_dir / "static"],
                OPENAI_API_KEY="test-key",
            ):
                with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                    openai_class.return_value.images.generate.return_value = ai_response
                    response = ThemeTemplateAdmin(
                        ThemeTemplate,
                        AdminSite(),
                    ).generate_selected_image_response(
                        selected_code=(
                            "{% static "
                            "'themes/eterna/assets/img/hero.jpg' %}"
                        ),
                        image_prompt="A bright modern office",
                        template_id=template.pk,
                    )

            payload = json.loads(response.content)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["code"], payload["image_url"])
            self.assertTrue(payload["code"].startswith("/media/ai-images/"))
            self.assertNotIn("{% static", payload["code"])

    def test_generates_exact_size_avif_and_replaces_only_image_source(self):
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            static_path = (
                base_dir
                / "static"
                / "themes"
                / "eterna"
                / "assets"
                / "img"
                / "hero.jpg"
            )
            static_path.parent.mkdir(parents=True)
            Image.new("RGB", (320, 180), "blue").save(static_path, format="JPEG")

            theme = Theme.objects.create(
                name="Eterna",
                slug="eterna",
                is_active=True,
            )
            template = ThemeTemplate.objects.create(
                theme=theme,
                name="Home",
                slug="home",
                template_type=TemplateType.PARENT_PAGE,
                is_active=True,
            )
            ai_response = SimpleNamespace(data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(
                        make_png((1024, 1024), "green")
                    ).decode("ascii")
                )
            ])
            selected = (
                '<img class="hero" '
                'src="{% static \'themes/eterna/assets/img/hero.jpg\' %}" '
                'alt="Original">'
            )

            with override_settings(
                BASE_DIR=base_dir,
                MEDIA_ROOT=base_dir / "media",
                STATICFILES_DIRS=[base_dir / "static"],
                OPENAI_API_KEY="test-key",
            ):
                with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                    openai_class.return_value.images.generate.return_value = ai_response
                    model_admin = ThemeTemplateAdmin(ThemeTemplate, AdminSite())
                    response = model_admin.generate_selected_image_response(
                        selected_code=selected,
                        image_prompt="A bright modern office",
                        template_id=template.pk,
                    )

                payload = json.loads(response.content)
                generated_path = base_dir / "media" / payload["storage_name"]

                self.assertEqual(response.status_code, 200)
                self.assertIn('class="hero"', payload["code"])
                self.assertIn('alt="Original"', payload["code"])
                self.assertIn(
                    f'src="{payload["image_url"]}"',
                    payload["code"],
                )
                self.assertEqual((payload["width"], payload["height"]), (320, 180))
                self.assertTrue(generated_path.exists())
                with Image.open(generated_path) as generated:
                    self.assertEqual(generated.format, "AVIF")
                    self.assertEqual(generated.size, (320, 180))

                call = openai_class.return_value.images.generate.call_args
                self.assertEqual(call.kwargs["model"], "gpt-image-2")
                self.assertEqual(call.kwargs["size"], "1536x1024")
                self.assertEqual(call.kwargs["quality"], "medium")
                self.assertIn("320x180", call.kwargs["prompt"])

    def test_resolves_relative_image_path_inside_current_theme(self):
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            static_path = (
                base_dir
                / "static"
                / "themes"
                / "eterna"
                / "assets"
                / "img"
                / "about.jpg"
            )
            static_path.parent.mkdir(parents=True)
            Image.new("RGB", (240, 300), "blue").save(static_path, format="JPEG")

            theme = Theme.objects.create(
                name="Eterna",
                slug="eterna",
                is_active=True,
            )
            template = ThemeTemplate.objects.create(
                theme=theme,
                name="About",
                slug="about",
                template_type=TemplateType.PARENT_PAGE,
                is_active=True,
            )
            ai_response = SimpleNamespace(data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(
                        make_png((1024, 1536), "green")
                    ).decode("ascii")
                )
            ])

            with override_settings(
                BASE_DIR=base_dir,
                MEDIA_ROOT=base_dir / "media",
                STATICFILES_DIRS=[base_dir / "static"],
                OPENAI_API_KEY="test-key",
            ):
                with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                    openai_class.return_value.images.generate.return_value = ai_response
                    response = ThemeTemplateAdmin(
                        ThemeTemplate,
                        AdminSite(),
                    ).generate_selected_image_response(
                        selected_code=(
                            '<img src="assets/img/about.jpg" alt="About">'
                        ),
                        image_prompt="A creative team meeting",
                        template_id=template.pk,
                    )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                openai_class.return_value.images.generate.call_args.kwargs["size"],
                "1024x1536",
            )

    def test_uses_svg_viewbox_dimensions_for_generated_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            static_path = (
                base_dir
                / "static"
                / "themes"
                / "moderna"
                / "assets"
                / "img"
                / "features-1.svg"
            )
            static_path.parent.mkdir(parents=True)
            static_path.write_text(
                '<svg viewBox="0 0 640 360" xmlns="http://www.w3.org/2000/svg">'
                '<path d="M0 0h640v360H0z"/>'
                "</svg>",
                encoding="utf-8",
            )

            theme = Theme.objects.create(
                name="Moderna",
                slug="moderna",
                is_active=True,
            )
            template = ThemeTemplate.objects.create(
                theme=theme,
                name="Home",
                slug="home",
                template_type=TemplateType.PARENT_PAGE,
                is_active=True,
            )
            ai_response = SimpleNamespace(data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(
                        make_png((1536, 1024), "green")
                    ).decode("ascii")
                )
            ])

            with override_settings(
                BASE_DIR=base_dir,
                MEDIA_ROOT=base_dir / "media",
                STATICFILES_DIRS=[base_dir / "static"],
                OPENAI_API_KEY="test-key",
            ):
                with patch("apps.theme_manager.admin.OpenAI") as openai_class:
                    openai_class.return_value.images.generate.return_value = ai_response
                    response = ThemeTemplateAdmin(
                        ThemeTemplate,
                        AdminSite(),
                    ).generate_selected_image_response(
                        selected_code=(
                            '<img src="{% static '
                            "'themes/moderna/assets/img/features-1.svg' %}"
                            '" alt="Features">'
                        ),
                        image_prompt="A modern SaaS dashboard illustration",
                        template_id=template.pk,
                    )

                payload = json.loads(response.content)
                generated_path = base_dir / "media" / payload["storage_name"]

                self.assertEqual(response.status_code, 200)
                self.assertEqual((payload["width"], payload["height"]), (640, 360))
                self.assertEqual(
                    openai_class.return_value.images.generate.call_args.kwargs["size"],
                    "1536x1024",
                )
                self.assertIn(f'src="{payload["image_url"]}"', payload["code"])
                with Image.open(generated_path) as generated:
                    self.assertEqual(generated.format, "AVIF")
                    self.assertEqual(generated.size, (640, 360))

    def test_returns_clear_error_when_static_image_does_not_exist(self):
        theme = Theme.objects.create(
            name="Eterna",
            slug="eterna",
            is_active=True,
        )
        template = ThemeTemplate.objects.create(
            theme=theme,
            name="Home",
            slug="home",
            template_type=TemplateType.PARENT_PAGE,
            is_active=True,
        )

        with tempfile.TemporaryDirectory() as directory:
            with override_settings(
                BASE_DIR=Path(directory),
                MEDIA_ROOT=Path(directory) / "media",
                STATICFILES_DIRS=[],
                OPENAI_API_KEY="test-key",
            ):
                with patch("apps.theme_manager.admin.OpenAI"):
                    response = ThemeTemplateAdmin(
                        ThemeTemplate,
                        AdminSite(),
                    ).generate_selected_image_response(
                        selected_code="{% static 'missing.jpg' %}",
                        image_prompt="A city skyline",
                        template_id=template.pk,
                    )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Static image not found", json.loads(response.content)["error"])
