from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps, UnidentifiedImageError
import pillow_avif  # noqa: F401 - registers AVIF support in Pillow


@dataclass(frozen=True)
class ImageSpec:
    min_size: tuple[int, int]
    output_size: tuple[int, int]
    output_format: str
    extension: str
    help_text: str
    quality: int | None = None
    ico_sizes: tuple[tuple[int, int], ...] = ()


SOCIAL_PREVIEW_SPEC = ImageSpec(
    min_size=(1200, 630),
    output_size=(1200, 630),
    output_format="JPEG",
    extension="jpg",
    quality=88,
    help_text=_(
        "Accepts JPEG, PNG, WebP, or AVIF. Minimum 1200 x 630 px. "
        "The image is center-cropped and saved as a 1200 x 630 JPEG."
    ),
)

ORGANIZATION_LOGO_SPEC = ImageSpec(
    min_size=(512, 512),
    output_size=(512, 512),
    output_format="PNG",
    extension="png",
    help_text=_(
        "Accepts JPEG, PNG, WebP, or AVIF. Minimum 512 x 512 px. "
        "The image is center-cropped and saved as a 512 x 512 PNG "
        "for the Organization logo in schema.org."
    ),
)

PERSON_IMAGE_SPEC = ImageSpec(
    min_size=(512, 512),
    output_size=(512, 512),
    output_format="PNG",
    extension="png",
    help_text=_(
        "Accepts JPEG, PNG, WebP, or AVIF. Minimum 512 x 512 px. "
        "The image is center-cropped and saved as a 512 x 512 PNG "
        "for the Person image in schema.org."
    ),
)

FAVICON_PNG_SPEC = ImageSpec(
    min_size=(512, 512),
    output_size=(512, 512),
    output_format="PNG",
    extension="png",
    help_text=_(
        "Accepts JPEG, PNG, WebP, or AVIF. Minimum 512 x 512 px. "
        "The image is center-cropped and saved as a 512 x 512 PNG."
    ),
)

APPLE_TOUCH_ICON_SPEC = ImageSpec(
    min_size=(180, 180),
    output_size=(180, 180),
    output_format="PNG",
    extension="png",
    help_text=_(
        "Accepts JPEG, PNG, WebP, or AVIF. Minimum 180 x 180 px. "
        "The image is center-cropped and saved as a 180 x 180 PNG."
    ),
)

FAVICON_ICO_SPEC = ImageSpec(
    min_size=(48, 48),
    output_size=(48, 48),
    output_format="ICO",
    extension="ico",
    ico_sizes=((16, 16), (32, 32), (48, 48)),
    help_text=_(
        "Accepts JPEG, PNG, WebP, or AVIF. Minimum 48 x 48 px. "
        "The image is center-cropped and saved as a multi-size ICO "
        "(16, 32, and 48 px)."
    ),
)


def _prepare_mode(image, output_format):
    if output_format == "JPEG":
        if image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        ):
            rgba_image = image.convert("RGBA")
            background = Image.new("RGB", rgba_image.size, "white")
            background.paste(rgba_image, mask=rgba_image.getchannel("A"))
            return background

        return image.convert("RGB")

    return image.convert("RGBA")


def process_uploaded_image(uploaded_file, spec):
    if not isinstance(uploaded_file, UploadedFile):
        return uploaded_file

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source:
            image = ImageOps.exif_transpose(source).copy()
    except (OSError, UnidentifiedImageError) as error:
        raise ValidationError(_("Upload a valid image file.")) from error

    width, height = image.size
    min_width, min_height = spec.min_size

    if width < min_width or height < min_height:
        raise ValidationError(
            f"Image must be at least {min_width} x {min_height} px; "
            f"uploaded image is {width} x {height} px."
        )

    image = ImageOps.fit(
        image,
        spec.output_size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    image = _prepare_mode(image, spec.output_format)

    output = BytesIO()
    save_options = {"format": spec.output_format}

    if spec.output_format == "JPEG":
        save_options.update(
            quality=spec.quality or 88,
            optimize=True,
            progressive=True,
        )
    elif spec.output_format == "PNG":
        save_options["optimize"] = True
    elif spec.output_format == "ICO":
        save_options["sizes"] = list(spec.ico_sizes)

    image.save(output, **save_options)
    output.seek(0)

    source_stem = Path(uploaded_file.name).stem or "image"
    output_width, output_height = spec.output_size
    output_name = (
        f"{source_stem}-{output_width}x{output_height}.{spec.extension}"
    )

    return ContentFile(output.read(), name=output_name)
