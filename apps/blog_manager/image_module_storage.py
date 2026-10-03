from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import shutil
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError
import pillow_avif  # noqa: F401 - registers AVIF support in Pillow


ALLOWED_EXTENSIONS = {".avif", ".jpeg", ".jpg", ".png", ".webp"}
MAX_FILES_PER_MODULE = 100
MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_MODULE_SIZE = 500 * 1024 * 1024
MAX_OUTPUT_DIMENSION = 1200
DESKTOP_CROP_SIZE = (600, 400)
MOBILE_CROP_SIZE = (380, 253)


def format_bytes(size):
    size = int(size or 0)
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _load_image(uploaded_file):
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source:
            image = ImageOps.exif_transpose(source).copy()
        uploaded_file.seek(0)
        return image
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ValidationError(
            f"{uploaded_file.name}: upload a valid raster image."
        ) from error


def validate_image_uploads(uploaded_files, existing_manifest):
    uploaded_files = list(uploaded_files or [])
    if len(existing_manifest) + len(uploaded_files) > MAX_FILES_PER_MODULE:
        raise ValidationError(
            f"An image module can contain no more than {MAX_FILES_PER_MODULE} files."
        )

    existing_size = sum(int(item.get("size") or 0) for item in existing_manifest)
    uploaded_size = 0
    for uploaded_file in uploaded_files:
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"{uploaded_file.name}: supported formats are JPEG, PNG, WebP and AVIF."
            )
        if uploaded_file.size > MAX_FILE_SIZE:
            raise ValidationError(
                f"{uploaded_file.name}: file exceeds the {format_bytes(MAX_FILE_SIZE)} limit."
            )
        uploaded_size += uploaded_file.size
        _load_image(uploaded_file)

    if existing_size + uploaded_size > MAX_MODULE_SIZE:
        raise ValidationError(
            f"The module would exceed its {format_bytes(MAX_MODULE_SIZE)} storage limit."
        )

    return uploaded_files


def _prepare_for_avif(image):
    image.thumbnail(
        (MAX_OUTPUT_DIMENSION, MAX_OUTPUT_DIMENSION),
        Image.Resampling.LANCZOS,
    )
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        return image.convert("RGBA")
    return image.convert("RGB")


def _crop_for_avif(image, size):
    cropped = ImageOps.fit(
        image,
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    return _prepare_mode_for_avif(cropped)


def _prepare_mode_for_avif(image):
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        return image.convert("RGBA")
    return image.convert("RGB")


def _avif_content(image, quality):
    output = BytesIO()
    image.save(output, format="AVIF", quality=quality)
    return ContentFile(output.getvalue())


def store_image_uploads(module, uploaded_files):
    entries = []
    for uploaded_file in uploaded_files:
        source_image = _load_image(uploaded_file)
        image = _prepare_for_avif(source_image.copy())
        desktop_crop = _crop_for_avif(source_image, DESKTOP_CROP_SIZE)
        mobile_crop = _crop_for_avif(source_image, MOBILE_CROP_SIZE)
        item_id = uuid.uuid4().hex
        relative_path = f"{module.storage_prefix}/{item_id}.avif"
        crop_path = f"{module.storage_prefix}/{item_id}_crop.avif"
        crop_mob_path = f"{module.storage_prefix}/{item_id}_crop_mob.avif"
        saved_paths = []
        try:
            saved_path = default_storage.save(
                relative_path,
                _avif_content(image, quality=85),
            )
            saved_paths.append(saved_path)
            saved_crop_path = default_storage.save(
                crop_path,
                _avif_content(desktop_crop, quality=60),
            )
            saved_paths.append(saved_crop_path)
            saved_crop_mob_path = default_storage.save(
                crop_mob_path,
                _avif_content(mobile_crop, quality=60),
            )
            saved_paths.append(saved_crop_mob_path)
        except Exception:
            for path in saved_paths:
                default_storage.delete(path)
            raise

        source_name = Path(uploaded_file.name).name
        alt_text = Path(source_name).stem.replace("-", " ").replace("_", " ").strip()
        stored_size = sum(default_storage.size(path) for path in saved_paths)
        entries.append({
            "id": item_id,
            "file": saved_path,
            "crop_file": saved_crop_path,
            "crop_mob_file": saved_crop_mob_path,
            "name": source_name,
            "alt": alt_text,
            "active": True,
            "size": stored_size,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })
    return entries


def delete_manifest_files(module, entries):
    prefix = f"{module.storage_prefix}/"
    for entry in entries:
        for field_name in ("file", "crop_file", "crop_mob_file"):
            file_name = str(entry.get(field_name) or "")
            if file_name.startswith(prefix):
                default_storage.delete(file_name)


def _delete_storage_prefix(prefix):
    try:
        directories, files = default_storage.listdir(prefix)
    except (FileNotFoundError, OSError):
        return

    for file_name in files:
        default_storage.delete(f"{prefix}/{file_name}")
    for directory in directories:
        _delete_storage_prefix(f"{prefix}/{directory}")


def delete_module_storage(module):
    prefix = module.storage_prefix.strip("/")

    try:
        storage_root = Path(default_storage.path("")).resolve()
        module_directory = Path(default_storage.path(prefix)).resolve()
    except (AttributeError, NotImplementedError):
        # Object storages use virtual folders. Deleting every object under the
        # prefix removes the folder automatically.
        _delete_storage_prefix(prefix)
        return

    if module_directory == storage_root or storage_root not in module_directory.parents:
        raise ValueError("Refusing to delete an image module outside media storage.")

    if module_directory.is_dir():
        shutil.rmtree(module_directory)


def manifest_with_urls(manifest):
    items = []
    for entry in manifest:
        item = dict(entry)
        for file_field, url_field in (
            ("file", "url"),
            ("crop_file", "crop_url"),
            ("crop_mob_file", "crop_mob_url"),
        ):
            file_name = item.get(file_field)
            item[url_field] = default_storage.url(file_name) if file_name else ""
        items.append(item)
    return items
