import base64
import io
import re
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pillow_avif  # noqa: F401
from PIL import Image, ImageOps
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import slugify
from unidecode import unidecode


STATIC_TAG_RE = re.compile(
    r"""{%\s*static\s+(['"])(?P<path>.+?)\1\s*%}""",
    re.IGNORECASE,
)
IMG_SRC_RE = re.compile(
    r"""(?P<prefix>\bsrc\s*=\s*)(?P<quote>['"])(?P<value>.*?)(?P=quote)""",
    re.IGNORECASE | re.DOTALL,
)
SVG_SIZE_RE = re.compile(
    r"""\b(?P<name>width|height)\s*=\s*["'](?P<value>[0-9.]+)(?:px|pt|rem|em|%)?["']""",
    re.IGNORECASE,
)
SVG_VIEWBOX_RE = re.compile(
    r"""\bviewBox\s*=\s*["']\s*(?P<x>-?[0-9.]+)\s+(?P<y>-?[0-9.]+)\s+(?P<width>[0-9.]+)\s+(?P<height>[0-9.]+)\s*["']""",
    re.IGNORECASE,
)
SVG_ROOT_RE = re.compile(r"""<svg\b[^>]*>""", re.IGNORECASE | re.DOTALL)


class ImageGenerationError(ValueError):
    pass


@dataclass(frozen=True)
class SelectedImage:
    selected_code: str
    source_value: str
    source_path: str
    replace_start: int
    replace_end: int

    def replace_source(self, new_url):
        return (
            self.selected_code[:self.replace_start]
            + new_url
            + self.selected_code[self.replace_end:]
        )


def parse_selected_image(selected_code):
    value = selected_code or ""
    if not value.strip():
        raise ImageGenerationError("Select an image path or an img tag.")

    source_start = len(value) - len(value.lstrip())
    source_end = len(value.rstrip())
    source_value = value[source_start:source_end]
    img_match = IMG_SRC_RE.search(value)
    if img_match:
        source_value = img_match.group("value")
        source_start, source_end = img_match.span("value")

    static_match = STATIC_TAG_RE.fullmatch(source_value.strip())
    if static_match:
        source_path = static_match.group("path").strip()
    else:
        source_path = source_value.strip().strip("\"'")

    source_path = source_path.split("?", 1)[0].split("#", 1)[0].strip()
    if not source_path:
        raise ImageGenerationError("The selected image path is empty.")

    return SelectedImage(
        selected_code=value,
        source_value=source_value,
        source_path=source_path,
        replace_start=source_start,
        replace_end=source_end,
    )


def open_source_image(source_path, theme_slug=""):
    static_url = str(getattr(settings, "STATIC_URL", "/static/"))
    media_url = str(getattr(settings, "MEDIA_URL", "/media/"))
    normalized = source_path.replace("\\", "/")

    if static_url and normalized.startswith(static_url):
        normalized = normalized[len(static_url):]
    elif normalized.startswith("/static/"):
        normalized = normalized[len("/static/"):]
    elif normalized.startswith("static/"):
        normalized = normalized[len("static/"):]

    if media_url and normalized.startswith(media_url):
        media_name = normalized[len(media_url):].lstrip("/")
        if not default_storage.exists(media_name):
            raise ImageGenerationError(f"Media image not found: {source_path}")
        return default_storage.open(media_name, "rb")
    if normalized.startswith("/media/"):
        media_name = normalized[len("/media/"):].lstrip("/")
        if not default_storage.exists(media_name):
            raise ImageGenerationError(f"Media image not found: {source_path}")
        return default_storage.open(media_name, "rb")

    normalized = normalized.lstrip("/")
    candidates = [normalized]
    if theme_slug and not normalized.startswith("themes/"):
        candidates.append(f"themes/{theme_slug}/{normalized}")

    for candidate in candidates:
        found_path = finders.find(candidate)
        if found_path:
            return open(found_path, "rb")

        local_static_path = Path(settings.BASE_DIR) / "static" / candidate
        if local_static_path.is_file():
            return local_static_path.open("rb")

    raise ImageGenerationError(
        f"Static image not found: {source_path}. "
        "Select a valid static/media path or an img tag."
    )


def get_source_dimensions(source_path, theme_slug=""):
    if source_path.split("?", 1)[0].split("#", 1)[0].lower().endswith(".svg"):
        return get_svg_dimensions(source_path, theme_slug=theme_slug)

    try:
        with open_source_image(source_path, theme_slug=theme_slug) as source_file:
            with Image.open(source_file) as image:
                image.load()
                return image.size
    except ImageGenerationError:
        raise
    except Exception as error:
        raise ImageGenerationError(
            f"Could not read the source image: {error}"
        ) from error


def get_svg_dimensions(source_path, theme_slug=""):
    try:
        with open_source_image(source_path, theme_slug=theme_slug) as source_file:
            svg = source_file.read(65536).decode("utf-8", errors="ignore")
    except ImageGenerationError:
        raise
    except Exception as error:
        raise ImageGenerationError(
            f"Could not read the source SVG: {error}"
        ) from error

    root_match = SVG_ROOT_RE.search(svg)
    root_tag = root_match.group(0) if root_match else svg

    sizes = {
        match.group("name").lower(): float(match.group("value"))
        for match in SVG_SIZE_RE.finditer(root_tag)
    }

    width = sizes.get("width")
    height = sizes.get("height")

    if not width or not height:
        viewbox_match = SVG_VIEWBOX_RE.search(root_tag)
        if viewbox_match:
            width = width or float(viewbox_match.group("width"))
            height = height or float(viewbox_match.group("height"))

    if not width or not height:
        return 1024, 1024

    return max(1, round(width)), max(1, round(height))


def get_generation_size(width, height):
    ratio = width / height
    if ratio >= 1.2:
        return "1536x1024"
    if ratio <= 0.83:
        return "1024x1536"
    return "1024x1024"


def build_image_prompt(user_prompt, width, height):
    orientation = "landscape" if width > height else "portrait" if height > width else "square"
    return f"""
Create a polished, original website image based on this instruction:
{user_prompt}

Image role and constraints:
- This image replaces an existing website asset.
- Final target dimensions: {width}x{height} pixels.
- Target aspect ratio: {width / height:.4f}:1 ({orientation}).
- Compose the main subject so a centered crop to the exact target aspect ratio remains natural.
- Keep important subjects and details away from the outer edges.
- Do not add text, captions, logos, watermarks, UI, frames, or borders unless explicitly requested.
- Use realistic detail and professional web-ready composition.
""".strip()


def decode_generated_image(response):
    if not getattr(response, "data", None):
        raise ImageGenerationError("OpenAI returned no image.")
    encoded = getattr(response.data[0], "b64_json", None)
    if not encoded:
        raise ImageGenerationError("OpenAI returned an empty image.")
    try:
        return base64.b64decode(encoded)
    except (ValueError, TypeError) as error:
        raise ImageGenerationError("OpenAI returned invalid image data.") from error


def build_output_name(theme_slug, user_prompt):
    prompt_slug = slugify(unidecode(user_prompt))[:60] or "generated-image"
    today = date.today()
    filename = f"{prompt_slug}-{uuid.uuid4().hex[:8]}.avif"
    return (
        f"ai-images/{slugify(theme_slug) or 'theme'}/"
        f"{today:%Y}/{today:%m}/{filename}"
    )


def convert_to_avif(image_bytes, width, height):
    try:
        with Image.open(io.BytesIO(image_bytes)) as generated:
            generated.load()
            generated = ImageOps.exif_transpose(generated).convert("RGB")
            fitted = ImageOps.fit(
                generated,
                (width, height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            output = io.BytesIO()
            fitted.save(
                output,
                format="AVIF",
                quality=82,
                speed=6,
            )
            return output.getvalue()
    except Exception as error:
        raise ImageGenerationError(
            f"Could not process the generated image: {error}"
        ) from error


def generate_replacement_image(client, selected_code, user_prompt, theme_slug):
    if not user_prompt:
        raise ImageGenerationError("Describe the image you want to generate.")

    selected_image = parse_selected_image(selected_code)
    width, height = get_source_dimensions(
        selected_image.source_path,
        theme_slug=theme_slug,
    )
    prompt = build_image_prompt(user_prompt, width, height)

    response = client.images.generate(
        model="gpt-image-2",
        prompt=prompt,
        size=get_generation_size(width, height),
        quality="medium",
        output_format="png",
    )
    generated_bytes = decode_generated_image(response)
    avif_bytes = convert_to_avif(generated_bytes, width, height)
    storage_name = default_storage.save(
        build_output_name(theme_slug, user_prompt),
        ContentFile(avif_bytes),
    )
    generated_url = default_storage.url(storage_name)

    return {
        "code": selected_image.replace_source(generated_url),
        "image_url": generated_url,
        "storage_name": storage_name,
        "width": width,
        "height": height,
    }
