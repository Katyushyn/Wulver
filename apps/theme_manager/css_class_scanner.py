import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.contrib.staticfiles import finders


TEMPLATE_DEPENDENCY_RE = re.compile(
    r"{%\s*(?:extends|include)\s+(['\"])(?P<name>.+?)\1(?:\s+[^%]*)?%}"
)
STATIC_CSS_RE = re.compile(
    r"{%\s*static\s+(['\"])(?P<path>[^'\"]+\.css(?:\?[^'\"]*)?)\1\s*%}"
)
RAW_STATIC_CSS_RE = re.compile(
    r"(?:href\s*=\s*|@import\s+)(['\"])(?:/static/)(?P<path>[^'\"]+\.css(?:\?[^'\"]*)?)\1",
    re.IGNORECASE,
)
CSS_IMPORT_RE = re.compile(
    r"@import\s+(?:url\(\s*)?(['\"]?)(?P<path>[^'\"\s)]+\.css(?:\?[^'\"\s)]*)?)\1\s*\)?",
    re.IGNORECASE,
)
HTML_CLASS_RE = re.compile(r"\bclass\s*=\s*(['\"])(?P<value>.*?)\1", re.IGNORECASE | re.DOTALL)
CLASS_NAME_RE = re.compile(r"^-?[_a-zA-Z]+[_a-zA-Z0-9-]*$")
CSS_CLASS_RE = re.compile(r"\.(-?[_a-zA-Z]+[_a-zA-Z0-9-]*)")


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _clean_asset_path(value):
    return unquote(urlsplit(value.strip()).path).lstrip("/")


def _resolve_template(name, current_path):
    name = name.strip().lstrip("/")
    candidates = [
        Path(settings.BASE_DIR) / "templates" / name,
        current_path.parent / name,
    ]
    for directory in getattr(settings, "TEMPLATES", ()):  # pragma: no branch
        for root in directory.get("DIRS", ()):
            candidates.append(Path(root) / name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def _resolve_static(path):
    normalized = _clean_asset_path(path)
    if normalized.startswith("static/"):
        normalized = normalized[len("static/"):]
    located = finders.find(normalized)
    if located:
        if isinstance(located, (list, tuple)):
            located = located[0] if located else None
        if located:
            return Path(located).resolve()
    fallback = Path(settings.BASE_DIR) / "static" / normalized
    return fallback.resolve() if fallback.is_file() else None


def _strip_css_noise(source):
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    source = re.sub(r"url\(.*?\)", " ", source, flags=re.IGNORECASE | re.DOTALL)
    source = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", " ", source, flags=re.DOTALL)
    return source


def _scan_css(path, classes, visited):
    path = path.resolve()
    if path in visited or not path.is_file():
        return
    visited.add(path)
    source = _read_text(path)
    if not source:
        return
    classes.update(CSS_CLASS_RE.findall(_strip_css_noise(source)))
    for match in CSS_IMPORT_RE.finditer(source):
        imported_source = match.group("path").strip()
        if imported_source.startswith(("http://", "https://", "//")):
            continue
        imported = _clean_asset_path(imported_source)
        imported_path = (path.parent / imported).resolve()
        if imported_path.is_file():
            _scan_css(imported_path, classes, visited)


def collect_template_css_classes(template_path):
    """Return the sorted CSS classes reachable from a saved template file."""
    classes = set()
    template_visited = set()
    css_visited = set()

    def scan_template(path):
        path = Path(path).resolve()
        if path in template_visited or not path.is_file():
            return
        template_visited.add(path)
        source = _read_text(path)
        if not source:
            return

        for match in HTML_CLASS_RE.finditer(source):
            class_value = re.sub(r"{{.*?}}|{%.*?%}", " ", match.group("value"), flags=re.DOTALL)
            for token in re.split(r"\s+", class_value.strip()):
                if CLASS_NAME_RE.fullmatch(token):
                    classes.add(token)

        static_paths = [match.group("path") for match in STATIC_CSS_RE.finditer(source)]
        static_paths.extend(match.group("path") for match in RAW_STATIC_CSS_RE.finditer(source))
        for static_path in static_paths:
            css_path = _resolve_static(static_path)
            if css_path:
                _scan_css(css_path, classes, css_visited)

        for match in TEMPLATE_DEPENDENCY_RE.finditer(source):
            dependency = _resolve_template(match.group("name"), path)
            if dependency:
                scan_template(dependency)

    scan_template(Path(template_path))
    return sorted(classes, key=lambda value: (value.lower(), value))
