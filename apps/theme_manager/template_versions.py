import hashlib
from pathlib import Path

from django.conf import settings
from django.template import engines
from django.utils import timezone

from .models import ThemeTemplateVersion


MAX_TEMPLATE_VERSIONS = 100


def normalize_template_code(code):
    if code is None:
        return ""
    return (
        code
        .replace("\r\r\n", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def get_template_code_hash(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def clear_template_loader_cache():
    for backend in engines.all():
        engine = getattr(backend, "engine", None)
        if not engine:
            continue
        for loader in engine.template_loaders:
            reset = getattr(loader, "reset", None)
            if reset:
                reset()


def create_template_snapshot(template, code, user=None, source="save"):
    normalized = normalize_template_code(code)
    code_hash = get_template_code_hash(normalized)
    latest = template.versions.only("code_hash").first()

    if latest and latest.code_hash == code_hash:
        return latest, False

    version = ThemeTemplateVersion.objects.create(
        template=template,
        code=normalized,
        code_hash=code_hash,
        line_count=len(normalized.splitlines()),
        source=source,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )

    obsolete_ids = list(
        template.versions
        .order_by("-created_at", "-pk")
        .values_list("pk", flat=True)[MAX_TEMPLATE_VERSIONS:]
    )
    if obsolete_ids:
        ThemeTemplateVersion.objects.filter(pk__in=obsolete_ids).delete()

    return version, True


def save_template_code(template, file_path, code, user=None, source="save"):
    path = Path(file_path)
    normalized = normalize_template_code(code)
    previous_code = None

    if path.exists():
        previous_code = normalize_template_code(
            path.read_bytes().decode("utf-8")
        )

    if previous_code == normalized:
        return False

    if previous_code is not None:
        create_template_snapshot(
            template=template,
            code=previous_code,
            user=user,
            source=source,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8", newline="\n")
    clear_template_loader_cache()
    template.__class__.objects.filter(pk=template.pk).update(
        updated_at=timezone.now()
    )
    return True
