import json
import uuid

from django.template.loader import render_to_string
from django.middleware.csrf import get_token

from .views import get_article_context, get_article_template


class ArticlePreviewError(Exception):
    pass


def _preview_bootstrap(marker):
    marker_json = json.dumps(marker)
    return f"""
<script>
(function () {{
    "use strict";
    var marker = {marker_json};
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_COMMENT);
    var start = null;
    var end = null;
    var node;

    while ((node = walker.nextNode())) {{
        if (node.nodeValue === marker + ":start") start = node;
        if (node.nodeValue === marker + ":end") end = node;
    }}
    if (!start || !end) return;

    function hideNode(target) {{
        if (target.nodeType === Node.ELEMENT_NODE) {{
            target.hidden = true;
            target.setAttribute("aria-hidden", "true");
            target.style.setProperty("display", "none", "important");
        }} else if (target.nodeType === Node.TEXT_NODE) {{
            target.nodeValue = "";
        }}
    }}

    function hideOutsideBoundary(boundary, hideBefore) {{
        var branch = boundary;
        while (branch && branch.parentNode) {{
            var parent = branch.parentNode;
            var siblings = Array.prototype.slice.call(parent.childNodes);
            var branchIndex = siblings.indexOf(branch);
            siblings.forEach(function (sibling, index) {{
                if ((hideBefore && index < branchIndex) || (!hideBefore && index > branchIndex)) {{
                    hideNode(sibling);
                }}
            }});
            if (parent === document.body) break;
            branch = parent;
        }}
    }}

    function isolateArticleBody() {{
        if (!start.isConnected || !end.isConnected) return;
        hideOutsideBoundary(start, true);
        hideOutsideBoundary(end, false);
    }}

    isolateArticleBody();
    var isolationScheduled = false;
    new MutationObserver(function () {{
        if (isolationScheduled) return;
        isolationScheduled = true;
        window.requestAnimationFrame(function () {{
            isolationScheduled = false;
            isolateArticleBody();
        }});
    }}).observe(document.body, {{childList: true, subtree: true}});

    document.documentElement.classList.add("wulver-article-body-preview");
    document.addEventListener("click", function (event) {{
        if (event.target.closest("a")) event.preventDefault();
    }}, true);
    document.addEventListener("submit", function (event) {{
        event.preventDefault();
    }}, true);
    window.scrollTo(0, 0);
}})();
</script>
"""


def render_article_body_preview(request, article, body_html):
    template = get_article_template(article)
    if not template:
        raise ArticlePreviewError("Article template is not configured.")

    marker = "wulver-article-preview-" + uuid.uuid4().hex
    article.body = (
        f"<!--{marker}:start-->"
        + body_html
        + f"<!--{marker}:end-->"
    )
    template_name = f"{template.theme.slug}/{template.slug}.html"
    context = get_article_context(request, article)
    context.update({
        "user": request.user,
        "csrf_token": get_token(request),
        "external_reviews": [],
        "reviews": [],
    })
    # Preview does not run global context processors: some of them call external
    # services, while all article context is already built above.
    rendered = render_to_string(template_name, context)
    bootstrap = _preview_bootstrap(marker)

    if "</body>" in rendered.lower():
        index = rendered.lower().rfind("</body>")
        return rendered[:index] + bootstrap + rendered[index:]
    return rendered + bootstrap
