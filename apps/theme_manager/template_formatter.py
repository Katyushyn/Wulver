import re


VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
RAW_TAGS = {"pre", "script", "style", "textarea"}
DJANGO_OPENERS = {
    "autoescape", "block", "blocktranslate", "comment", "filter", "for",
    "if", "ifchanged", "spaceless", "verbatim", "with",
}
DJANGO_CLOSERS = {
    "endautoescape", "endblock", "endblocktranslate", "endcomment",
    "endfilter", "endfor", "endif", "endifchanged", "endspaceless",
    "endverbatim", "endwith",
}
DJANGO_BRANCHES = {"elif", "else", "empty"}


def _read_until(code, start, ending):
    end = code.find(ending, start)
    return len(code) if end == -1 else end + len(ending)


def _read_html_tag(code, start):
    quote = None
    index = start + 1
    while index < len(code):
        char = code[index]
        if quote:
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == ">":
            return index + 1
        index += 1
    return len(code)


def _html_tag_name(token):
    match = re.match(r"<\s*/?\s*([A-Za-z][\w:-]*)", token)
    return match.group(1).lower() if match else ""


def tokenize_template(code):
    tokens = []
    index = 0
    text_start = 0

    def append_text(end):
        value = code[text_start:end]
        if value.strip():
            tokens.append(("text", value.strip()))

    while index < len(code):
        token_type = None
        end = index

        if code.startswith("<!--", index):
            token_type = "html_comment"
            end = _read_until(code, index + 4, "-->")
        elif code.startswith("{#", index):
            token_type = "django_comment"
            end = _read_until(code, index + 2, "#}")
        elif code.startswith("{%", index):
            token_type = "django_block"
            end = _read_until(code, index + 2, "%}")
        elif code.startswith("{{", index):
            token_type = "django_variable"
            end = _read_until(code, index + 2, "}}")
        elif code[index] == "<":
            candidate_end = _read_html_tag(code, index)
            candidate = code[index:candidate_end]
            if re.match(r"<\s*(?:!DOCTYPE\b|/?[A-Za-z])", candidate, re.I):
                token_type = "html_tag"
                end = candidate_end

        if not token_type:
            index += 1
            continue

        append_text(index)
        token = code[index:end].strip()
        tokens.append((token_type, token))

        if token_type == "html_tag":
            tag_name = _html_tag_name(token)
            is_opening = (
                tag_name in RAW_TAGS
                and not re.match(r"<\s*/", token)
                and not token.rstrip().endswith("/>")
            )
            if is_opening:
                closing_match = re.search(
                    rf"</\s*{re.escape(tag_name)}\s*>",
                    code[end:],
                    re.IGNORECASE,
                )
                if closing_match:
                    raw_end = end + closing_match.start()
                    raw_content = code[end:raw_end]
                    if raw_content:
                        tokens.append(("raw", raw_content))
                    closing_end = end + closing_match.end()
                    tokens.append(("html_tag", code[raw_end:closing_end].strip()))
                    end = closing_end

        index = end
        text_start = end

    append_text(len(code))
    return tokens


def _django_tag_name(token):
    content = token[2:-2].strip()
    return content.split(None, 1)[0] if content else ""


def _is_html_closer(token):
    return bool(re.match(r"<\s*/", token))


def _is_html_opener(token):
    if _is_html_closer(token) or token.startswith("<!"):
        return False
    tag_name = _html_tag_name(token)
    return (
        bool(tag_name)
        and tag_name not in VOID_TAGS
        and not token.rstrip().endswith("/>")
    )


def _dedent_raw_lines(lines):
    lines = list(lines)

    while lines and not lines[0].strip():
        lines.pop(0)

    while lines and not lines[-1].strip():
        lines.pop()

    non_empty_lines = [line for line in lines if line.strip()]

    if not non_empty_lines:
        return ["" for line in lines]

    common_indent = min(
        len(line) - len(line.lstrip(" \t"))
        for line in non_empty_lines
    )

    if common_indent == 0:
        return lines

    return [
        line[common_indent:] if line.strip() else ""
        for line in lines
    ]


def format_template_code(code, indent_size=4):
    tokens = tokenize_template((code or "").replace("\r\n", "\n").replace("\r", "\n"))
    lines = []
    indent = 0

    for token_type, token in tokens:
        if token_type == "raw":
            raw_lines = _dedent_raw_lines(token.strip("\n").splitlines())
            for raw_line in raw_lines:
                if raw_line.strip():
                    lines.append((" " * (indent * indent_size)) + raw_line.rstrip())
                else:
                    lines.append("")
            continue

        django_tag = (
            _django_tag_name(token)
            if token_type == "django_block"
            else ""
        )
        decreases_before = (
            token_type == "html_tag" and _is_html_closer(token)
        ) or django_tag in DJANGO_CLOSERS or django_tag in DJANGO_BRANCHES
        if decreases_before:
            indent = max(0, indent - 1)

        token_lines = token.splitlines() or [""]
        for token_line in token_lines:
            stripped = token_line.strip()
            if stripped:
                lines.append((" " * (indent * indent_size)) + stripped)

        increases_after = (
            token_type == "html_tag" and _is_html_opener(token)
        ) or django_tag in DJANGO_OPENERS or django_tag in DJANGO_BRANCHES
        if increases_after:
            indent += 1

    return "\n".join(lines).strip() + ("\n" if lines else "")
