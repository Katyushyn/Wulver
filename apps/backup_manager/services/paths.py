from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from apps.backup_manager.models import BackupSettings


class BackupPathError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupRoot:
    name: str
    path: Path
    kind: str

    @property
    def archive_prefix(self):
        return f"roots/{self.name}"


def _resolved(value):
    if not value:
        return None
    return Path(value).expanduser().resolve()


def _is_inside(path, parent):
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def collect_backup_roots(configuration=None):
    configuration = configuration or BackupSettings.get_solo()
    project = _resolved(settings.BASE_DIR)
    if not project or not project.exists():
        raise BackupPathError("Django BASE_DIR does not exist.")

    candidates = [BackupRoot("project", project, "project")]

    for name, setting_name, kind in (
        ("static", "STATIC_ROOT", "static"),
        ("media", "MEDIA_ROOT", "media"),
    ):
        path = _resolved(getattr(settings, setting_name, None))
        if path and path.exists():
            candidates.append(BackupRoot(name, path, kind))

    template_index = 0
    for engine in getattr(settings, "TEMPLATES", ()):
        for value in engine.get("DIRS", ()):
            path = _resolved(value)
            if path and path.exists():
                template_index += 1
                candidates.append(BackupRoot(f"templates_{template_index}", path, "templates"))

    for index, path in enumerate(configuration.get_additional_paths(), start=1):
        if not path.exists():
            raise BackupPathError(f"Additional backup path does not exist: {path}")
        candidates.append(BackupRoot(f"external_{index}", path, "external"))

    roots = []
    seen = set()
    for candidate in candidates:
        if candidate.path in seen:
            continue
        if any(_is_inside(candidate.path, root.path) for root in roots if root.path.is_dir()):
            continue
        containing_existing = [
            root
            for root in roots
            if candidate.path.is_dir() and _is_inside(root.path, candidate.path)
        ]
        if containing_existing:
            raise BackupPathError(
                f"Overlapping backup roots are ambiguous: {candidate.path} contains "
                + ", ".join(str(root.path) for root in containing_existing)
            )
        roots.append(candidate)
        seen.add(candidate.path)

    backup_directory = configuration.resolved_backup_directory
    for root in roots:
        if root.path == backup_directory or _is_inside(backup_directory, root.path):
            raise BackupPathError(
                f"Backup directory must be outside every backed-up root: {backup_directory} is inside {root.path}."
            )

    return tuple(roots)


def current_restore_targets(configuration=None):
    configuration = configuration or BackupSettings.get_solo()
    targets = {"project": _resolved(settings.BASE_DIR)}
    static_root = _resolved(getattr(settings, "STATIC_ROOT", None))
    media_root = _resolved(getattr(settings, "MEDIA_ROOT", None))
    if static_root:
        targets["static"] = static_root
    if media_root:
        targets["media"] = media_root

    template_index = 0
    for engine in getattr(settings, "TEMPLATES", ()):
        for value in engine.get("DIRS", ()):
            template_index += 1
            path = _resolved(value)
            if path:
                targets[f"templates_{template_index}"] = path

    for index, path in enumerate(configuration.get_additional_paths(), start=1):
        targets[f"external_{index}"] = path
    return targets
