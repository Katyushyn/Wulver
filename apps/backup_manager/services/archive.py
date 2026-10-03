import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from django import get_version as get_django_version
from django.conf import settings
from django.db import connections
from django.utils import timezone

from apps.backup_manager.models import BackupSettings, BackupSnapshot
from apps.backup_manager.services.database import DatabaseBackupError, get_database_adapter
from apps.backup_manager.services.paths import (
    BackupPathError,
    collect_backup_roots,
    current_restore_targets,
)


ARCHIVE_FORMAT = "wulver-full-backup"
ARCHIVE_VERSION = 1


class BackupArchiveError(RuntimeError):
    pass


def _pyzipper():
    try:
        import pyzipper
    except ImportError as error:
        raise BackupArchiveError(
            "AES ZIP support is unavailable. Install the pyzipper dependency."
        ) from error
    return pyzipper


def _password_bytes(password):
    value = str(password or "")
    if not value:
        raise BackupArchiveError("A backup password is required.")
    return value.encode("utf-8")


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_git_revision():
    head = Path(settings.BASE_DIR) / ".git" / "HEAD"
    try:
        value = head.read_text(encoding="utf-8").strip()
        if value.startswith("ref: "):
            reference = Path(settings.BASE_DIR) / ".git" / value[5:]
            if reference.is_file():
                return reference.read_text(encoding="utf-8").strip()
        return value
    except OSError:
        return ""


def _sqlite_database_files():
    paths = set()
    config = settings.DATABASES.get("default", {})
    engine = str(config.get("ENGINE") or "")
    name = config.get("NAME")
    if name and engine.endswith("sqlite3") and str(name) != ":memory:":
        database = Path(name).expanduser().resolve()
        paths.update(
            {
                database,
                Path(f"{database}-wal"),
                Path(f"{database}-shm"),
                Path(f"{database}-journal"),
            }
        )
    return paths


def _logical_root_manifest(physical_roots, configuration):
    logical_targets = current_restore_targets(configuration)
    entries = []
    for name, path in logical_targets.items():
        path = Path(path).resolve()
        if not path.exists():
            continue
        containers = []
        for root in physical_roots:
            try:
                relative = path.relative_to(root.path.resolve())
            except ValueError:
                continue
            containers.append((len(root.path.parts), root, relative))
        if not containers:
            continue
        _length, physical, relative = max(containers, key=lambda value: value[0])
        archive_prefix = PurePosixPath(physical.archive_prefix)
        if relative.parts:
            archive_prefix = archive_prefix.joinpath(*relative.parts)
        if name == "project":
            kind = "project"
        elif name in {"static", "media"}:
            kind = name
        elif name.startswith("templates_"):
            kind = "templates"
        else:
            kind = "external"
        entries.append(
            {
                "name": name,
                "kind": kind,
                "original_path": str(path),
                "archive_prefix": archive_prefix.as_posix(),
            }
        )
    return entries


def _zip_info(zip_file, archive_name, path, *, is_directory=False, is_symlink=False):
    try:
        timestamp = datetime.fromtimestamp(path.lstat().st_mtime)
        date_time = (
            max(timestamp.year, 1980),
            timestamp.month,
            timestamp.day,
            timestamp.hour,
            timestamp.minute,
            timestamp.second,
        )
    except OSError:
        date_time = datetime.now().timetuple()[:6]
    info = zip_file.zipinfo_cls(filename=archive_name, date_time=date_time)
    info.create_system = 3
    try:
        mode = stat.S_IMODE(path.lstat().st_mode)
    except OSError:
        mode = 0o755 if is_directory else 0o644
    type_bits = stat.S_IFLNK if is_symlink else stat.S_IFDIR if is_directory else stat.S_IFREG
    info.external_attr = (type_bits | mode) << 16
    if is_directory:
        info.external_attr |= 0x10
    return info


def _write_path(zip_file, source, archive_name, *, excluded_files):
    source = Path(source)
    archive_name = PurePosixPath(archive_name).as_posix()

    if source.is_symlink():
        zip_file.writestr(
            _zip_info(zip_file, archive_name, source, is_symlink=True),
            os.readlink(source).encode("utf-8"),
        )
        return 1, len(os.readlink(source).encode("utf-8"))

    if source.is_file():
        if source.resolve() in excluded_files:
            return 0, 0
        zip_file.write(source, archive_name)
        return 1, source.stat().st_size

    if not source.is_dir():
        return 0, 0

    file_count = 0
    source_size = 0
    zip_file.writestr(
        _zip_info(zip_file, f"{archive_name.rstrip('/')}/", source, is_directory=True),
        b"",
    )
    for child in sorted(source.iterdir(), key=lambda item: item.name):
        child_count, child_size = _write_path(
            zip_file,
            child,
            f"{archive_name.rstrip('/')}/{child.name}",
            excluded_files=excluded_files,
        )
        file_count += child_count
        source_size += child_size
    return file_count, source_size


def _validate_member_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise BackupArchiveError(f"Unsafe ZIP member path: {name}")


def read_backup_manifest(archive_path, password):
    pyzipper = _pyzipper()
    try:
        with pyzipper.AESZipFile(archive_path, "r") as archive:
            archive.setpassword(_password_bytes(password))
            for info in archive.infolist():
                _validate_member_name(info.filename)
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    except (KeyError, ValueError, RuntimeError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise BackupArchiveError(
            "The backup is invalid, damaged, or the password is incorrect."
        ) from error

    if manifest.get("format") != ARCHIVE_FORMAT or manifest.get("version") != ARCHIVE_VERSION:
        raise BackupArchiveError("This ZIP is not a supported Wulver full backup.")
    if not isinstance(manifest.get("database"), dict) or not isinstance(manifest.get("roots"), list):
        raise BackupArchiveError("The backup manifest is incomplete.")
    return manifest


def create_backup_archive(snapshot, password):
    configuration = BackupSettings.get_solo()
    password_bytes = _password_bytes(password)
    backup_root = configuration.resolved_backup_directory
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(backup_root, 0o700)
    except OSError:
        pass

    snapshot.status = BackupSnapshot.Status.RUNNING
    snapshot.started_at = timezone.now()
    snapshot.error_message = ""
    snapshot.save(update_fields=("status", "started_at", "error_message", "updated_at"))

    pyzipper = _pyzipper()
    timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    archive_name = f"wulver-{timestamp}-{str(snapshot.pk)[:8]}.zip"
    final_archive = backup_root / archive_name
    partial_archive = backup_root / f".{archive_name}.partial"

    try:
        roots = collect_backup_roots(configuration)
        adapter = get_database_adapter("default")
        with tempfile.TemporaryDirectory(prefix=".wulver-backup-", dir=backup_root) as temporary:
            temporary_path = Path(temporary)
            database_directory = temporary_path / "database"
            database_directory.mkdir()
            dump_name = f"default{adapter.extension}"
            dump_path = database_directory / dump_name
            adapter.create_dump(dump_path)

            manifest = {
                "format": ARCHIVE_FORMAT,
                "version": ARCHIVE_VERSION,
                "created_at": datetime.now(UTC).isoformat(),
                "snapshot_id": str(snapshot.pk),
                "description": snapshot.description,
                "django_version": get_django_version(),
                "git_revision": _archive_git_revision(),
                "database": adapter.manifest(f"database/{dump_name}"),
                "roots": _logical_root_manifest(roots, configuration),
            }

            compression = zipfile.ZIP_STORED if configuration.compression_level == 0 else zipfile.ZIP_DEFLATED
            with pyzipper.AESZipFile(
                partial_archive,
                "w",
                compression=compression,
                compresslevel=configuration.compression_level if compression == zipfile.ZIP_DEFLATED else None,
                encryption=pyzipper.WZ_AES,
                allowZip64=True,
            ) as archive:
                archive.setpassword(password_bytes)
                archive.setencryption(pyzipper.WZ_AES, nbits=256)
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                )
                archive.write(dump_path, f"database/{dump_name}")

                file_count = 0
                source_size = dump_path.stat().st_size
                excluded_files = _sqlite_database_files()
                for root in roots:
                    count, size = _write_path(
                        archive,
                        root.path,
                        root.archive_prefix,
                        excluded_files=excluded_files,
                    )
                    file_count += count
                    source_size += size

            os.chmod(partial_archive, 0o600)
            os.replace(partial_archive, final_archive)
            manifest["statistics"] = {
                "files": file_count,
                "source_bytes": source_size,
                "archive_bytes": final_archive.stat().st_size,
            }

        # Reopen the encrypted central directory and manifest before publishing the record.
        read_backup_manifest(final_archive, password)
        snapshot.status = BackupSnapshot.Status.COMPLETED
        snapshot.archive_path = str(final_archive)
        snapshot.storage_root = str(backup_root)
        snapshot.archive_name = archive_name
        snapshot.archive_size = final_archive.stat().st_size
        snapshot.sha256 = _sha256(final_archive)
        snapshot.database_vendor = adapter.vendor
        snapshot.manifest = manifest
        snapshot.completed_at = timezone.now()
        snapshot.save()
        return snapshot
    except Exception as error:
        partial_archive.unlink(missing_ok=True)
        snapshot.status = BackupSnapshot.Status.FAILED
        snapshot.error_message = str(error)
        snapshot.completed_at = timezone.now()
        snapshot.save(update_fields=("status", "error_message", "completed_at", "updated_at"))
        if isinstance(error, (BackupArchiveError, BackupPathError, DatabaseBackupError)):
            raise
        raise BackupArchiveError(str(error)) from error


def verify_backup_archive(snapshot, password, *, full=True):
    path = snapshot.archive_file
    if not path or not path.is_file():
        raise BackupArchiveError("Backup ZIP does not exist.")
    if snapshot.sha256 and _sha256(path) != snapshot.sha256:
        raise BackupArchiveError("Backup SHA-256 does not match the stored checksum.")
    manifest = read_backup_manifest(path, password)
    if full:
        pyzipper = _pyzipper()
        try:
            with pyzipper.AESZipFile(path, "r") as archive:
                archive.setpassword(_password_bytes(password))
                damaged = archive.testzip()
        except (RuntimeError, zipfile.BadZipFile) as error:
            raise BackupArchiveError("Backup verification failed.") from error
        if damaged:
            raise BackupArchiveError(f"Damaged file in backup: {damaged}")
    if snapshot.manifest.get("statistics") and "statistics" not in manifest:
        manifest["statistics"] = snapshot.manifest["statistics"]
    snapshot.verified_at = timezone.now()
    snapshot.manifest = manifest
    snapshot.save(update_fields=("verified_at", "manifest", "updated_at"))
    return manifest


def import_backup_archive(uploaded_file, password, *, created_by=None, description=""):
    configuration = BackupSettings.get_solo()
    limit = configuration.maximum_upload_size_mb * 1024 * 1024
    if uploaded_file.size > limit:
        raise BackupArchiveError(
            f"Uploaded backup exceeds the {configuration.maximum_upload_size_mb} MB limit."
        )
    backup_root = configuration.resolved_backup_directory
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    identifier = uuid.uuid4()
    archive_name = f"wulver-uploaded-{timezone.now():%Y%m%d-%H%M%S}-{str(identifier)[:8]}.zip"
    partial = backup_root / f".{archive_name}.partial"
    final = backup_root / archive_name
    try:
        with partial.open("wb") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        os.chmod(partial, 0o600)
        manifest = read_backup_manifest(partial, password)
        os.replace(partial, final)
        snapshot = BackupSnapshot.objects.create(
            id=identifier,
            description=description,
            status=BackupSnapshot.Status.COMPLETED,
            source=BackupSnapshot.Source.UPLOADED,
            archive_path=str(final),
            storage_root=str(backup_root),
            archive_name=archive_name,
            archive_size=final.stat().st_size,
            sha256=_sha256(final),
            database_vendor=str(manifest.get("database", {}).get("vendor") or ""),
            manifest=manifest,
            created_by=created_by,
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )
        return snapshot
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def _extract_archive(archive_path, password, destination):
    pyzipper = _pyzipper()
    destination = Path(destination).resolve()
    links = []
    with pyzipper.AESZipFile(archive_path, "r") as archive:
        archive.setpassword(_password_bytes(password))
        for info in archive.infolist():
            _validate_member_name(info.filename)
            relative = PurePosixPath(info.filename)
            target = destination.joinpath(*relative.parts)
            try:
                target.resolve().relative_to(destination)
            except ValueError as error:
                raise BackupArchiveError(f"Unsafe ZIP member path: {info.filename}") from error
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                links.append((info, target))
                continue
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                if mode:
                    os.chmod(target, stat.S_IMODE(mode))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            if mode:
                os.chmod(target, stat.S_IMODE(mode))

        for info, target in links:
            link_value = archive.read(info).decode("utf-8")
            link_path = Path(link_value)
            if link_path.is_absolute():
                raise BackupArchiveError(f"Absolute symlink is not allowed in backup: {info.filename}")
            try:
                (target.parent / link_path).resolve().relative_to(destination)
            except ValueError as error:
                raise BackupArchiveError(f"Unsafe symlink in backup: {info.filename}") from error
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(link_value)


def _copy_restored_root(staged, target, identifier):
    staged = Path(staged)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = target.with_name(f".{target.name}.wulver-before-restore-{identifier}")
    if previous.exists():
        raise BackupArchiveError(f"Temporary restore path already exists: {previous}")
    if target.exists() or target.is_symlink():
        os.replace(target, previous)
    else:
        previous = None
    try:
        if staged.is_dir():
            shutil.copytree(staged, target, symlinks=True)
        else:
            shutil.copy2(staged, target, follow_symlinks=False)
    except Exception:
        if target.exists():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        if previous:
            os.replace(previous, target)
        raise
    return previous


def restore_backup_archive(snapshot, password):
    manifest = verify_backup_archive(snapshot, password, full=True)
    configuration = BackupSettings.get_solo()
    configuration_values = {
        "backup_directory": configuration.backup_directory,
        "additional_paths": configuration.additional_paths,
        "compression_level": configuration.compression_level,
        "maximum_upload_size_mb": configuration.maximum_upload_size_mb,
    }
    snapshot_values = {
        "description": snapshot.description,
        "source": snapshot.source,
        "archive_path": snapshot.archive_path,
        "storage_root": snapshot.storage_root,
        "archive_name": snapshot.archive_name,
        "archive_size": snapshot.archive_size,
        "sha256": snapshot.sha256,
        "database_vendor": snapshot.database_vendor,
        "manifest": snapshot.manifest,
        "started_at": snapshot.started_at,
        "verified_at": snapshot.verified_at,
    }
    backup_root = configuration.resolved_backup_directory
    identifier = str(snapshot.pk)[:8]
    snapshot.status = BackupSnapshot.Status.RESTORING
    snapshot.error_message = ""
    snapshot.save(update_fields=("status", "error_message", "updated_at"))

    replacements = []
    try:
        with tempfile.TemporaryDirectory(prefix=".wulver-restore-", dir=backup_root) as temporary:
            staging = Path(temporary)
            _extract_archive(snapshot.archive_file, password, staging)
            current_targets = current_restore_targets(configuration)
            for root in manifest["roots"]:
                staged = staging.joinpath(*PurePosixPath(root["archive_prefix"]).parts)
                if not staged.exists() and not staged.is_symlink():
                    raise BackupArchiveError(f"Backup root is missing: {root['name']}")
                target = current_targets.get(root["name"])
                if target is None:
                    target = Path(root["original_path"]).expanduser().resolve()
                previous = _copy_restored_root(staged, target, identifier)
                replacements.append((Path(target), previous))

            database_manifest = manifest["database"]
            dump_path = staging.joinpath(*PurePosixPath(database_manifest["dump_file"]).parts)
            if not dump_path.is_file():
                raise BackupArchiveError("Database dump is missing from the backup.")
            adapter = get_database_adapter(
                database_manifest.get("alias", "default"),
                expected_adapter=database_manifest.get("adapter"),
            )
            adapter.restore_dump(dump_path, database_manifest)

            BackupSettings.objects.update_or_create(pk=1, defaults=configuration_values)
            BackupSnapshot.objects.update_or_create(
                pk=snapshot.pk,
                defaults={
                    **snapshot_values,
                    "status": BackupSnapshot.Status.COMPLETED,
                    "error_message": "",
                    "completed_at": timezone.now(),
                },
            )

        for _target, previous in replacements:
            if previous and previous.exists():
                if previous.is_dir() and not previous.is_symlink():
                    shutil.rmtree(previous)
                else:
                    previous.unlink()

        restart_file = Path(settings.BASE_DIR) / "tmp" / "restart.txt"
        restart_file.parent.mkdir(parents=True, exist_ok=True)
        restart_file.touch()
        return manifest
    except Exception as error:
        for target, previous in reversed(replacements):
            try:
                if target.exists() or target.is_symlink():
                    if target.is_dir() and not target.is_symlink():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if previous and previous.exists():
                    os.replace(previous, target)
            except OSError:
                pass
        try:
            snapshot.status = BackupSnapshot.Status.FAILED
            snapshot.error_message = str(error)
            snapshot.completed_at = timezone.now()
            snapshot.save(update_fields=("status", "error_message", "completed_at", "updated_at"))
        except Exception:
            pass
        if isinstance(error, (BackupArchiveError, BackupPathError, DatabaseBackupError)):
            raise
        raise BackupArchiveError(str(error)) from error
