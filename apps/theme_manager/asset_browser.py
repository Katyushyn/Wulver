import os
import tempfile
from pathlib import Path, PurePosixPath

from django.conf import settings


IMAGE_EXTENSIONS = {
    ".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp",
}
UPLOAD_IMAGE_EXTENSIONS = IMAGE_EXTENSIONS - {".svg"}
MAX_IMAGE_UPLOAD_SIZE = 20 * 1024 * 1024


class AssetUploadError(ValueError):
    pass


class AssetDeleteError(ValueError):
    pass


def _format_size(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _asset_data(file_path, root, asset_type):
    relative_path = file_path.relative_to(root).as_posix()
    stat = file_path.stat()
    if asset_type == "static":
        preview_url = str(settings.STATIC_URL).rstrip("/") + "/" + relative_path
        insert_value = "{% static '" + relative_path + "' %}"
    else:
        media_url = str(settings.MEDIA_URL).rstrip("/") + "/" + relative_path
        preview_url = media_url
        insert_value = media_url

    return {
        "type": asset_type,
        "name": file_path.name,
        "path": relative_path,
        "preview_url": preview_url,
        "insert_value": insert_value,
        "size": stat.st_size,
        "size_display": _format_size(stat.st_size),
        "extension": file_path.suffix.lower().lstrip("."),
        "version": stat.st_mtime_ns,
    }


def _collect_directory_assets(root, asset_type):
    root = Path(root)
    if not root.is_dir():
        return []

    assets = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        resolved = file_path.resolve()
        resolved_root = root.resolve()
        if resolved_root not in resolved.parents:
            continue

        assets.append(_asset_data(file_path, root, asset_type))
    return assets


def collect_image_assets():
    static_assets = []
    seen_static_paths = set()
    for static_root in settings.STATICFILES_DIRS:
        for asset in _collect_directory_assets(static_root, "static"):
            if asset["path"] in seen_static_paths:
                continue
            seen_static_paths.add(asset["path"])
            static_assets.append(asset)

    media_assets = _collect_directory_assets(settings.MEDIA_ROOT, "media")
    assets = static_assets + media_assets
    return sorted(
        assets,
        key=lambda item: (
            0 if item["type"] == "media" else 1,
            item["path"].lower(),
        ),
    )


def _normalize_asset_path(value, allowed_extensions=None):
    allowed_extensions = allowed_extensions or UPLOAD_IMAGE_EXTENSIONS
    raw_path = str(value or "").strip().replace("\\", "/")
    parts = raw_path.split("/")
    invalid_characters = set('<>:"|?*')

    if (
        not raw_path
        or raw_path.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
        or any(any(character in invalid_characters for character in part) for part in parts)
        or any(part.endswith((" ", ".")) for part in parts)
    ):
        raise AssetUploadError("Enter a valid relative image path.")

    normalized = PurePosixPath(*parts)
    if normalized.suffix.lower() not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise AssetUploadError(f"Unsupported image extension. Allowed: {allowed}.")

    return normalized.as_posix()


def _resolve_upload_target(asset_type, relative_path):
    if asset_type == "media":
        roots = [Path(settings.MEDIA_ROOT)]
    elif asset_type == "static":
        roots = [Path(root) for root in settings.STATICFILES_DIRS]
    else:
        raise AssetUploadError("Choose either static or media storage.")

    if not roots:
        raise AssetUploadError(f"No {asset_type} upload directory is configured.")

    for root in roots:
        existing = root / Path(relative_path)
        if existing.is_file():
            return root, existing

    root = roots[0]
    return root, root / Path(relative_path)


def _resolve_existing_asset(asset_type, relative_path):
    if asset_type == "media":
        roots = [Path(settings.MEDIA_ROOT)]
    elif asset_type == "static":
        roots = [Path(root) for root in settings.STATICFILES_DIRS]
    else:
        raise AssetDeleteError("Choose either static or media storage.")

    for root in roots:
        asset_path = root / Path(relative_path)
        resolved_root = root.resolve()
        resolved_asset_path = asset_path.resolve()
        if resolved_asset_path == resolved_root or resolved_root not in resolved_asset_path.parents:
            raise AssetDeleteError("The target path is outside the asset directory.")
        if asset_path.is_file():
            return asset_path

    raise AssetDeleteError("Image file not found.")


def delete_image_asset(asset_type, path):
    try:
        relative_path = _normalize_asset_path(
            path,
            allowed_extensions=IMAGE_EXTENSIONS,
        )
    except AssetUploadError as error:
        raise AssetDeleteError(str(error)) from error

    asset_path = _resolve_existing_asset(asset_type, relative_path)
    asset_path.unlink()
    return {
        "type": asset_type,
        "path": relative_path,
    }


def delete_image_assets(asset_items):
    deleted = []
    failed = []

    for item in asset_items:
        asset_type = str(item.get("type", "")).strip()
        path = str(item.get("path", "")).strip()
        try:
            deleted.append(delete_image_asset(asset_type, path))
        except (AssetDeleteError, OSError) as error:
            failed.append({
                "type": asset_type,
                "path": path,
                "error": str(error) or "Image could not be deleted.",
            })

    return deleted, failed


def save_uploaded_image(
    uploaded_file,
    asset_type,
    target_path,
    overwrite=False,
    default_static_prefix="",
):
    if not uploaded_file:
        raise AssetUploadError("Choose an image to upload.")
    if uploaded_file.size > MAX_IMAGE_UPLOAD_SIZE:
        raise AssetUploadError("The image is larger than the 20 MB upload limit.")

    source_extension = Path(uploaded_file.name).suffix.lower()
    if source_extension not in UPLOAD_IMAGE_EXTENSIONS:
        raise AssetUploadError("The selected file is not a supported raster image.")

    relative_path = _normalize_asset_path(target_path)
    if (
        asset_type == "static"
        and default_static_prefix
        and not relative_path.startswith("themes/")
    ):
        relative_path = _normalize_asset_path(
            str(PurePosixPath(default_static_prefix) / relative_path)
        )
    target_extension = Path(relative_path).suffix.lower()
    equivalent_extensions = {source_extension, target_extension} <= {".jpg", ".jpeg"}
    if source_extension != target_extension and not equivalent_extensions:
        raise AssetUploadError("The target extension must match the uploaded image.")

    root, destination = _resolve_upload_target(asset_type, relative_path)
    resolved_root = root.resolve()
    resolved_destination = destination.resolve()
    if resolved_root not in resolved_destination.parents:
        raise AssetUploadError("The target path is outside the upload directory.")

    existed = destination.exists()
    if existed and not overwrite:
        raise AssetUploadError(
            "An image with this path already exists. Confirm replacement to overwrite it."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".asset-upload-",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            for chunk in uploaded_file.chunks():
                temporary_file.write(chunk)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()

    return _asset_data(destination, root, asset_type), existed
