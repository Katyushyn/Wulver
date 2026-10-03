import re
import shlex
from collections import defaultdict
from html.parser import HTMLParser

from django.template import Engine, TemplateSyntaxError
from django.template.base import Lexer, TokenType


VOID_HTML_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
OPTIONAL_END_TAGS = {
    "li", "dt", "dd", "p", "rt", "rp", "optgroup", "option",
    "colgroup", "thead", "tbody", "tfoot", "tr", "td", "th",
}
DJANGO_BLOCK_PAIRS = {
    "autoescape": "endautoescape",
    "block": "endblock",
    "blocktranslate": "endblocktranslate",
    "comment": "endcomment",
    "filter": "endfilter",
    "for": "endfor",
    "if": "endif",
    "ifchanged": "endifchanged",
    "spaceless": "endspaceless",
    "verbatim": "endverbatim",
    "with": "endwith",
}
DJANGO_CLOSERS = {
    closer: opener for opener, closer in DJANGO_BLOCK_PAIRS.items()
}
URL_ATTRIBUTE_RE = re.compile(
    r"""\b(?P<attribute>src|href|poster|action)\s*=\s*(?P<quote>['"])(?P<value>.*?)(?P=quote)""",
    re.IGNORECASE | re.DOTALL,
)
SRCSET_ATTRIBUTE_RE = re.compile(
    r"""\bsrcset\s*=\s*(?P<quote>['"])(?P<value>.*?)(?P=quote)""",
    re.IGNORECASE | re.DOTALL,
)
CSS_URL_RE = re.compile(
    r"""url\(\s*(?P<quote>['"]?)(?P<value>.*?)(?P=quote)\s*\)""",
    re.IGNORECASE,
)
STATIC_TAG_RE = re.compile(
    r"""{%\s*static\s+(['"])(?P<path>.*?)\1\s*%}""",
    re.IGNORECASE,
)
ID_ATTRIBUTE_RE = re.compile(
    r"""\bid\s*=\s*(['"])(?P<value>.*?)\1""",
    re.IGNORECASE | re.DOTALL,
)


class TemplateHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in OPTIONAL_END_TAGS and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        if tag not in VOID_HTML_TAGS:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        return

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in VOID_HTML_TAGS:
            return
        matching_index = next(
            (
                index
                for index in range(len(self.stack) - 1, -1, -1)
                if self.stack[index][0] == tag
            ),
            None,
        )
        if matching_index is None:
            self.errors.append({
                "line": self.getpos()[0],
                "message": f"Unexpected closing </{tag}>.",
            })
            return

        dangling = self.stack[matching_index + 1:]
        for dangling_tag, dangling_line in reversed(dangling):
            if dangling_tag not in OPTIONAL_END_TAGS:
                self.errors.append({
                    "line": dangling_line,
                    "message": (
                        f"<{dangling_tag}> is not closed before </{tag}>."
                    ),
                })
        del self.stack[matching_index:]

    def finish(self):
        for tag, line in reversed(self.stack):
            if tag not in OPTIONAL_END_TAGS:
                self.errors.append({
                    "line": line,
                    "message": f"Unclosed <{tag}> tag.",
                })
        return self.errors


def _split_token(contents):
    try:
        return shlex.split(contents)
    except ValueError:
        return contents.split()


def collect_template_symbols(code):
    loaded = {}
    used_tags = set()
    used_filters = set()
    ignored_until = None

    for token in Lexer(code or "").tokenize():
        if token.token_type == TokenType.BLOCK:
            bits = _split_token(token.contents)
            if not bits:
                continue

            tag_name = bits[0]
            if ignored_until:
                if tag_name == ignored_until:
                    ignored_until = None
                continue

            if tag_name == "comment":
                ignored_until = "endcomment"
                continue
            if tag_name == "verbatim":
                ignored_until = "endverbatim"
                continue

            if tag_name == "load":
                if "from" in bits:
                    from_index = bits.index("from")
                    if from_index + 1 < len(bits):
                        library_name = bits[from_index + 1]
                        selected = set(bits[1:from_index])
                        previous = loaded.get(library_name)
                        loaded[library_name] = (previous or set()) | selected
                else:
                    for library_name in bits[1:]:
                        loaded[library_name] = None
                continue

            used_tags.add(tag_name)
            used_filters.update(re.findall(r"\|\s*([A-Za-z_]\w*)", token.contents))

        elif token.token_type == TokenType.VAR:
            used_filters.update(re.findall(r"\|\s*([A-Za-z_]\w*)", token.contents))

    return loaded, used_tags, used_filters


def _line_number(code, index):
    return code.count("\n", 0, index) + 1


def analyze_html_structure(code):
    cleaned = re.sub(r"{#.*?#}", "", code or "", flags=re.DOTALL)
    cleaned = re.sub(r"{%.*?%}", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"{{.*?}}", "template_value", cleaned, flags=re.DOTALL)
    parser = TemplateHTMLParser()
    try:
        parser.feed(cleaned)
        parser.close()
    except Exception as error:
        parser.errors.append({
            "line": parser.getpos()[0],
            "message": f"HTML parsing failed: {error}",
        })
    return parser.finish()


def analyze_django_blocks(code):
    stack = []
    errors = []

    for token in Lexer(code or "").tokenize():
        if token.token_type != TokenType.BLOCK:
            continue
        bits = _split_token(token.contents)
        if not bits:
            continue
        tag_name = bits[0]
        line = getattr(token, "lineno", None)

        if tag_name in DJANGO_BLOCK_PAIRS:
            stack.append((tag_name, DJANGO_BLOCK_PAIRS[tag_name], line))
        elif tag_name in DJANGO_CLOSERS:
            if not stack:
                errors.append({
                    "line": line,
                    "message": f"Unexpected {{% {tag_name} %}}.",
                })
                continue
            opener, expected_closer, opener_line = stack[-1]
            if tag_name != expected_closer:
                errors.append({
                    "line": line,
                    "message": (
                        f"{{% {tag_name} %}} closes {{% {opener} %}} "
                        f"from line {opener_line}; expected "
                        f"{{% {expected_closer} %}}."
                    ),
                })
                continue
            stack.pop()

    for opener, closer, line in reversed(stack):
        errors.append({
            "line": line,
            "message": (
                f"Unclosed {{% {opener} %}} block; "
                f"expected {{% {closer} %}}."
            ),
        })
    return errors


def analyze_asset_urls(code):
    issues = []
    seen = set()

    def add_issue(index, message):
        key = (index, message)
        if key in seen:
            return
        seen.add(key)
        issues.append({
            "line": _line_number(code, index),
            "message": message,
        })

    for match in STATIC_TAG_RE.finditer(code or ""):
        path = match.group("path").strip()
        if path.startswith(("/media/", "media/")):
            add_issue(
                match.start(),
                "Media URL is wrapped in {% static %}; use the /media/... URL directly.",
            )
        elif path.startswith(("/static/", "static/")):
            add_issue(
                match.start(),
                "Path inside {% static %} must not include the static/ prefix.",
            )
        elif path.startswith(("http://", "https://", "//")):
            add_issue(
                match.start(),
                "External URL must not be wrapped in {% static %}.",
            )

    for match in URL_ATTRIBUTE_RE.finditer(code or ""):
        value = match.group("value").strip()
        attribute = match.group("attribute").lower()
        if value.startswith(("media/", "./media/", "../media/")):
            add_issue(
                match.start(),
                f'{attribute}="{value}" is a relative media URL; use /media/...',
            )
        elif value.startswith(("static/", "./static/", "../static/", "/static/")):
            add_issue(
                match.start(),
                (
                    f'{attribute}="{value}" is a raw static URL; '
                    "use {% static 'path' %}."
                ),
            )
        elif "{% static" in value and "/media/" in value:
            add_issue(
                match.start(),
                "Media URL is wrapped in {% static %}; use the media URL directly.",
            )

    for match in SRCSET_ATTRIBUTE_RE.finditer(code or ""):
        candidates = [
            candidate.strip().split()[0]
            for candidate in match.group("value").split(",")
            if candidate.strip()
        ]
        for candidate in candidates:
            if candidate.startswith(("media/", "./media/", "../media/")):
                add_issue(
                    match.start(),
                    f'srcset contains relative media URL "{candidate}"; use /media/...',
                )
            elif candidate.startswith(
                ("static/", "./static/", "../static/", "/static/")
            ):
                add_issue(
                    match.start(),
                    (
                        f'srcset contains raw static URL "{candidate}"; '
                        "use Django static tags."
                    ),
                )

    for match in CSS_URL_RE.finditer(code or ""):
        value = match.group("value").strip()
        if value.startswith(("media/", "./media/", "../media/")):
            add_issue(
                match.start(),
                f'CSS url("{value}") is a relative media URL; use /media/...',
            )
        elif value.startswith(("static/", "./static/", "../static/", "/static/")):
            add_issue(
                match.start(),
                (
                    f'CSS url("{value}") is a raw static URL; '
                    "use a Django static tag."
                ),
            )
    return issues


def analyze_duplicate_ids(code):
    occurrences = defaultdict(list)
    for match in ID_ATTRIBUTE_RE.finditer(code or ""):
        value = match.group("value").strip()
        if not value or "{{" in value or "{%" in value:
            continue
        occurrences[value].append(_line_number(code, match.start()))

    return [
        {
            "id": value,
            "lines": lines,
            "message": f'Duplicate id="{value}" on lines {", ".join(map(str, lines))}.',
        }
        for value, lines in sorted(occurrences.items())
        if len(lines) > 1
    ]


def analyze_template_loads(code):
    engine = Engine.get_default()
    loaded, used_tags, used_filters = collect_template_symbols(code)

    builtin_tags = set()
    builtin_filters = set()
    for library in engine.template_builtins:
        builtin_tags.update(library.tags)
        builtin_filters.update(library.filters)

    tag_libraries = defaultdict(set)
    filter_libraries = defaultdict(set)
    for library_name, library in engine.template_libraries.items():
        for tag_name in library.tags:
            tag_libraries[tag_name].add(library_name)
        for filter_name in library.filters:
            filter_libraries[filter_name].add(library_name)

    used_by_library = defaultdict(set)
    missing_by_library = defaultdict(set)
    ambiguous = []

    def is_loaded(library_name, symbol):
        if library_name not in loaded:
            return False
        selected = loaded[library_name]
        return selected is None or symbol in selected

    def classify(symbol, candidates):
        loaded_candidates = sorted(
            library_name for library_name in candidates
            if is_loaded(library_name, symbol)
        )
        if loaded_candidates:
            used_by_library[loaded_candidates[0]].add(symbol)
        elif len(candidates) == 1:
            missing_by_library[next(iter(candidates))].add(symbol)
        elif len(candidates) > 1:
            ambiguous.append({
                "symbol": symbol,
                "libraries": sorted(candidates),
            })

    for tag_name in sorted(used_tags - builtin_tags):
        classify(tag_name, tag_libraries.get(tag_name, set()))
    for filter_name in sorted(used_filters - builtin_filters):
        classify(filter_name, filter_libraries.get(filter_name, set()))

    unused = []
    unknown = []
    for library_name, selected in loaded.items():
        library = engine.template_libraries.get(library_name)
        if not library:
            unknown.append(library_name)
            continue

        available = set(library.tags) | set(library.filters)
        if selected is not None:
            available &= selected
        if not ((used_tags | used_filters) & available):
            unused.append(library_name)

    syntax_errors = []
    try:
        engine.from_string(code or "")
    except TemplateSyntaxError as error:
        syntax_errors.append(str(error))

    return {
        "missing": [
            {
                "library": library_name,
                "symbols": sorted(symbols),
                "statement": "{% load " + library_name + " %}",
            }
            for library_name, symbols in sorted(missing_by_library.items())
        ],
        "unused": sorted(unused),
        "unknown": sorted(unknown),
        "ambiguous": ambiguous,
        "syntax_errors": syntax_errors,
        "django_block_errors": analyze_django_blocks(code or ""),
        "html_errors": analyze_html_structure(code or ""),
        "url_issues": analyze_asset_urls(code or ""),
        "duplicate_ids": analyze_duplicate_ids(code or ""),
    }
