(function () {
    "use strict";

    var editors = [];
    var lastImageInsertion = {key: "", time: 0};

    function label(message) {
        return typeof window.gettext === "function" ? window.gettext(message) : message;
    }

    function csrfToken() {
        var input = document.querySelector("input[name='csrfmiddlewaretoken']");
        return input ? input.value : "";
    }

    function isVisible(element) {
        return Boolean(
            element
            && (element.offsetWidth || element.offsetHeight || element.getClientRects().length)
        );
    }

    function createButton(icon, title, callback) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "article-code-toolbar__button";
        button.title = label(title);
        button.setAttribute("aria-label", label(title));
        var symbol = document.createElement("span");
        symbol.className = "material-symbols-outlined";
        symbol.setAttribute("aria-hidden", "true");
        symbol.textContent = icon;
        button.appendChild(symbol);
        button.addEventListener("click", callback);
        return button;
    }

    function createGroup(toolbar, name) {
        var group = document.createElement("div");
        group.className = "article-code-toolbar__group";
        group.setAttribute("role", "group");
        group.setAttribute("aria-label", label(name));
        toolbar.appendChild(group);
        return group;
    }

    function replaceSelection(editor, replacement, selectFrom, selectTo) {
        var from = editor.getCursor("from");
        var startIndex = editor.indexFromPos(from);
        editor.replaceSelection(replacement, "around", "+article-toolbar");
        if (typeof selectFrom === "number" && typeof selectTo === "number") {
            editor.setSelection(
                editor.posFromIndex(startIndex + selectFrom),
                editor.posFromIndex(startIndex + selectTo)
            );
        }
        editor.focus();
    }

    function wrapSelection(editor, opening, closing, placeholder) {
        var selected = editor.getSelection();
        var content = selected || placeholder || label("Text");
        replaceSelection(
            editor,
            opening + content + closing,
            selected ? undefined : opening.length,
            selected ? undefined : opening.length + content.length
        );
    }

    function wrapBlock(editor, tag, attributes, placeholder) {
        var opening = "<" + tag + (attributes ? " " + attributes : "") + ">";
        wrapSelection(editor, opening, "</" + tag + ">", placeholder);
    }

    function insertList(editor, ordered) {
        var selected = editor.getSelection();
        var lines = (selected || label("List item"))
            .split(/\r?\n/)
            .map(function (line) { return line.trim(); })
            .filter(Boolean);
        var tag = ordered ? "ol" : "ul";
        var items = lines.map(function (line) {
            return "    <li>" + line + "</li>";
        }).join("\n");
        replaceSelection(editor, "<" + tag + ">\n" + items + "\n</" + tag + ">\n");
    }

    function insertCode(editor) {
        var selected = editor.getSelection();
        if (selected.indexOf("\n") !== -1) {
            var escaped = selected
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;");
            replaceSelection(editor, "<pre><code>" + escaped + "</code></pre>");
            return;
        }
        wrapSelection(editor, "<code>", "</code>", label("Code"));
    }

    function insertLink(editor) {
        var url = window.prompt(label("Enter the link URL:"), "https://");
        if (!url || !url.trim()) {
            return;
        }
        wrapSelection(
            editor,
            '<a href="' + url.trim().replace(/"/g, "&quot;") + '">',
            "</a>",
            label("Link text")
        );
    }

    function openSiteLinks(state) {
        if (!window.WulverCmsLinkBrowser) {
            window.alert(label("CMS link browser is not available."));
            return;
        }
        window.WulverCmsLinkBrowser.open({
            endpoint: state.textarea.dataset.cmsLinkOptionsUrl,
            language: state.textarea.dataset.language,
            editor: state.editor,
            valueKey: "url",
            insertAnchorWithoutSelection: true,
            includeReference: false,
        });
    }

    function insertCssClassAtCursor(editor, cursor, className) {
        var value = editor.getValue();
        var index = editor.indexFromPos(cursor);
        var tagStart = value.lastIndexOf("<", index);
        var tagEndBefore = value.lastIndexOf(">", index);
        var tagEnd = value.indexOf(">", index);

        if (tagStart > tagEndBefore && tagEnd !== -1 && value.charAt(tagStart + 1) !== "/") {
            var openingTag = value.slice(tagStart, tagEnd + 1);
            var relativeIndex = index - tagStart;
            var classMatch = /\bclass\s*=\s*(["'])(.*?)\1/i.exec(openingTag);
            if (classMatch) {
                var valueStart = classMatch.index + classMatch[0].indexOf(classMatch[2]);
                var valueEnd = valueStart + classMatch[2].length;
                if (relativeIndex >= valueStart && relativeIndex <= valueEnd) {
                    var before = value.charAt(index - 1);
                    var after = value.charAt(index);
                    var insertion = (before && !/\s/.test(before) ? " " : "")
                        + className
                        + (after && !/\s|["']/.test(after) ? " " : "");
                    editor.replaceRange(insertion, cursor, cursor, "+css-class");
                    editor.setCursor(editor.posFromIndex(index + insertion.length));
                    editor.focus();
                    return;
                }
            } else {
                var insertionPoint = tagEnd;
                if (value.charAt(tagEnd - 1) === "/") insertionPoint -= 1;
                var attribute = ' class="' + className + '"';
                var position = editor.posFromIndex(insertionPoint);
                editor.replaceRange(attribute, position, position, "+css-class");
                editor.setCursor(editor.posFromIndex(insertionPoint + attribute.length));
                editor.focus();
                return;
            }
        }

        editor.replaceRange(className, cursor, cursor, "+css-class");
        editor.setCursor(editor.posFromIndex(index + className.length));
        editor.focus();
    }

    function openCssClassPicker(state) {
        var form = state.textarea.closest("form");
        var categoryInput = form && form.querySelector("[name='category']");
        var templateInput = form && form.querySelector("[name='theme_template']");
        if (!categoryInput || !categoryInput.value) {
            window.alert(label("Select an article category first."));
            return;
        }
        if (!state.textarea.dataset.cssClassesUrl) {
            window.alert(label("CSS class list URL is not configured."));
            return;
        }

        var cursor = state.editor.getCursor();
        var endpoint = new URL(state.textarea.dataset.cssClassesUrl, window.location.origin);
        endpoint.searchParams.set("category_id", categoryInput.value);
        if (templateInput && templateInput.value) {
            endpoint.searchParams.set("theme_template_id", templateInput.value);
        }

        window.fetch(endpoint.toString(), {
            headers: {"X-Requested-With": "XMLHttpRequest"},
        }).then(function (response) {
            return response.json().then(function (payload) {
                if (!response.ok) throw new Error(payload.error || label("CSS classes could not be loaded."));
                return payload;
            });
        }).then(function (payload) {
            var classes = Array.isArray(payload.classes) ? payload.classes : [];
            if (!classes.length) {
                window.alert(label("No CSS classes were detected. Save the Article Parent template first."));
                return;
            }

            var backdrop = document.createElement("div");
            backdrop.className = "template-code-modal-backdrop";
            var modal = document.createElement("div");
            modal.className = "template-code-modal template-code-cms-link-modal";
            modal.innerHTML =
                '<div class="template-code-modal-header">'
                + '<div class="template-code-modal-title"></div>'
                + '<button type="button" class="template-code-modal-close"></button>'
                + '</div>'
                + '<div class="template-code-cms-link-controls">'
                + '<input type="search" class="template-code-cms-link-search" autocomplete="off">'
                + '<span class="template-code-cms-link-status"></span>'
                + '</div>'
                + '<div class="template-code-modal-list template-code-cms-link-list"></div>';
            backdrop.appendChild(modal);
            document.body.appendChild(backdrop);

            var title = modal.querySelector(".template-code-modal-title");
            var close = modal.querySelector(".template-code-modal-close");
            var search = modal.querySelector(".template-code-cms-link-search");
            var status = modal.querySelector(".template-code-cms-link-status");
            var list = modal.querySelector(".template-code-modal-list");
            title.textContent = label("CSS classes") + " — " + (payload.template ? payload.template.name : "");
            close.textContent = label("Close");
            search.placeholder = label("Search by class name prefix");

            function dismiss() {
                backdrop.remove();
                state.editor.focus();
            }
            function render() {
                var query = search.value.trim().toLowerCase();
                var filtered = classes.filter(function (name) {
                    return !query || name.toLowerCase().startsWith(query);
                });
                var visible = filtered.slice(0, 100);
                list.replaceChildren();
                visible.forEach(function (className) {
                    var option = document.createElement("button");
                    option.type = "button";
                    option.className = "template-code-modal-option";
                    option.textContent = className;
                    option.addEventListener("click", function () {
                        dismiss();
                        insertCssClassAtCursor(state.editor, cursor, className);
                        state.editor.save();
                    });
                    list.appendChild(option);
                });
                status.textContent = visible.length + " / " + filtered.length;
            }
            close.addEventListener("click", dismiss);
            backdrop.addEventListener("click", function (event) {
                if (event.target === backdrop) dismiss();
            });
            search.addEventListener("input", render);
            render();
            search.focus();
        }).catch(function (error) {
            window.alert(error.message || label("CSS classes could not be loaded."));
        });
    }

    function scrollRatio(scrollTop, scrollHeight, clientHeight) {
        var maximum = Math.max(0, scrollHeight - clientHeight);
        return maximum ? Math.max(0, Math.min(1, scrollTop / maximum)) : 0;
    }

    function editorScrollRatio(editor) {
        var info = editor.getScrollInfo();
        return scrollRatio(info.top, info.height, info.clientHeight);
    }

    function previewScrollRatio(state) {
        var previewWindow = state.previewFrame.contentWindow;
        var previewDocument = state.previewFrame.contentDocument;
        if (!previewWindow || !previewDocument) {
            return 0;
        }
        var root = previewDocument.documentElement;
        var body = previewDocument.body;
        var height = Math.max(root.scrollHeight, body ? body.scrollHeight : 0);
        return scrollRatio(previewWindow.scrollY, height, previewWindow.innerHeight);
    }

    var previewBlockTags = new Set([
        "address", "article", "aside", "blockquote", "details", "div", "dl",
        "fieldset", "figcaption", "figure", "h1", "h2", "h3", "h4", "h5",
        "h6", "hr", "img", "li", "main", "ol", "p", "pre", "section",
        "summary", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    ]);

    function instrumentPreviewHtml(html) {
        var anchors = [];
        var output = [];
        var cursor = 0;
        var index = 0;
        var rawTextTag = "";

        function findTagEnd(start) {
            var quote = "";
            var position;
            for (position = start + 1; position < html.length; position += 1) {
                var character = html.charAt(position);
                if (quote) {
                    if (character === quote) quote = "";
                } else if (character === '"' || character === "'") {
                    quote = character;
                } else if (character === ">") {
                    return position;
                }
            }
            return -1;
        }

        while (index < html.length) {
            if (rawTextTag) {
                var closeIndex = html.toLowerCase().indexOf("</" + rawTextTag, index);
                if (closeIndex === -1) break;
                index = closeIndex;
                rawTextTag = "";
            }
            if (html.slice(index, index + 4) === "<!--") {
                var commentEnd = html.indexOf("-->", index + 4);
                index = commentEnd === -1 ? html.length : commentEnd + 3;
                continue;
            }
            if (html.charAt(index) !== "<") {
                index += 1;
                continue;
            }

            var tagEnd = findTagEnd(index);
            if (tagEnd === -1) break;
            var tagSource = html.slice(index, tagEnd + 1);
            var openingMatch = tagSource.match(/^<\s*([a-zA-Z][\w:-]*)/);
            var closingMatch = tagSource.match(/^<\s*\/\s*([a-zA-Z][\w:-]*)/);
            if (openingMatch && !closingMatch) {
                var tagName = openingMatch[1].toLowerCase();
                if (previewBlockTags.has(tagName)) {
                    var anchorId = "wulver-block-" + anchors.length;
                    var nameEnd = index + openingMatch[0].length;
                    output.push(html.slice(cursor, nameEnd));
                    output.push(' data-wulver-preview-anchor="' + anchorId + '"');
                    cursor = nameEnd;
                    anchors.push({id: anchorId, sourceIndex: index});
                }
                if (["script", "style", "textarea"].indexOf(tagName) !== -1) {
                    rawTextTag = tagName;
                }
            }
            index = tagEnd + 1;
        }
        output.push(html.slice(cursor));
        return {html: output.join(""), anchors: anchors};
    }

    function editorCenterIndex(editor) {
        var info = editor.getScrollInfo();
        var centerLine = editor.lineAtHeight(info.top + (info.clientHeight / 2), "local");
        return editor.indexFromPos({line: centerLine, ch: 0});
    }

    function nearestEditorAnchor(anchors, sourceIndex) {
        var selected = anchors.length ? anchors[0] : null;
        anchors.some(function (anchor) {
            if (anchor.sourceIndex > sourceIndex) return true;
            selected = anchor;
            return false;
        });
        return selected;
    }

    function previewAnchorAtCenter(state) {
        var previewWindow = state.previewFrame.contentWindow;
        var previewDocument = state.previewFrame.contentDocument;
        if (!previewWindow || !previewDocument) return null;
        var element = previewDocument.elementFromPoint(
            Math.max(0, previewWindow.innerWidth / 2),
            Math.max(0, previewWindow.innerHeight / 2)
        );
        var anchored = element && element.closest("[data-wulver-preview-anchor]");
        if (anchored) return anchored.getAttribute("data-wulver-preview-anchor");

        var center = previewWindow.innerHeight / 2;
        var best = null;
        previewDocument.querySelectorAll("[data-wulver-preview-anchor]").forEach(function (candidate) {
            var bounds = candidate.getBoundingClientRect();
            if (bounds.bottom >= 0 && bounds.top <= center) best = candidate;
        });
        return best && best.getAttribute("data-wulver-preview-anchor");
    }

    function scrollEditorToAnchor(state, anchorId, fallbackRatio) {
        var anchor = state.previewAnchors.find(function (item) { return item.id === anchorId; });
        if (!anchor) {
            var fallbackInfo = state.editor.getScrollInfo();
            state.editor.scrollTo(
                null,
                fallbackRatio * Math.max(0, fallbackInfo.height - fallbackInfo.clientHeight)
            );
            return;
        }
        var position = state.editor.posFromIndex(anchor.sourceIndex);
        var coordinates = state.editor.charCoords(position, "local");
        var info = state.editor.getScrollInfo();
        state.editor.scrollTo(null, Math.max(0, coordinates.top - (info.clientHeight / 2)));
    }

    function scrollPreviewToAnchor(state, anchorId, fallbackRatio) {
        var previewWindow = state.previewFrame.contentWindow;
        var previewDocument = state.previewFrame.contentDocument;
        if (!previewWindow || !previewDocument) return;
        var target = anchorId
            ? previewDocument.querySelector('[data-wulver-preview-anchor="' + anchorId + '"]')
            : null;
        if (target) {
            var bounds = target.getBoundingClientRect();
            previewWindow.scrollTo(
                0,
                Math.max(0, previewWindow.scrollY + bounds.top - (previewWindow.innerHeight / 2))
            );
            return;
        }
        var root = previewDocument.documentElement;
        var body = previewDocument.body;
        var height = Math.max(root.scrollHeight, body ? body.scrollHeight : 0);
        previewWindow.scrollTo(0, fallbackRatio * Math.max(0, height - previewWindow.innerHeight));
    }

    function setPreviewButtonState(state, previewVisible) {
        var symbol = state.previewButton.querySelector(".material-symbols-outlined");
        var title = previewVisible ? label("HTML code") : label("Visual preview");
        symbol.textContent = previewVisible ? "code" : "visibility";
        state.previewButton.title = title;
        state.previewButton.setAttribute("aria-label", title);
        state.previewButton.setAttribute("aria-pressed", previewVisible ? "true" : "false");
        state.previewButton.classList.toggle("is-active", previewVisible);
    }

    function showHtmlEditor(state) {
        var ratio = state.previewVisible ? previewScrollRatio(state) : 0;
        var anchorId = state.previewVisible ? previewAnchorAtCenter(state) : null;
        state.previewVisible = false;
        state.previewFrame.hidden = true;
        state.wrapper.hidden = false;
        setPreviewButtonState(state, false);
        state.editor.refresh();
        scrollEditorToAnchor(state, anchorId, ratio);
        state.editor.focus();
    }

    async function showVisualPreview(state) {
        var form = state.textarea.closest("form");
        var categoryInput = form && form.querySelector("[name='category']");
        var templateInput = form && form.querySelector("[name='theme_template']");
        var language = state.textarea.dataset.language || "";
        var titleInput = form && (
            form.querySelector("[name='title_" + language + "']")
            || form.querySelector("[name='title']")
        );

        if (!categoryInput || !categoryInput.value) {
            window.alert(label("Select an article category first."));
            return;
        }
        if (!state.textarea.dataset.previewUrl) {
            window.alert(label("Article preview URL is not configured."));
            return;
        }

        var ratio = editorScrollRatio(state.editor);
        var instrumented = instrumentPreviewHtml(state.editor.getValue());
        var activeAnchor = nearestEditorAnchor(
            instrumented.anchors,
            editorCenterIndex(state.editor)
        );
        state.previewAnchors = instrumented.anchors;
        var formData = new FormData();
        formData.append("body_html", instrumented.html);
        formData.append("category_id", categoryInput.value);
        formData.append("theme_template_id", templateInput ? templateInput.value : "");
        formData.append("article_id", state.textarea.dataset.articleId || "");
        formData.append("language", language);
        formData.append("title", titleInput ? titleInput.value : "");
        state.previewButton.disabled = true;
        state.toolbar.classList.add("is-busy");

        try {
            var response = await window.fetch(state.textarea.dataset.previewUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: formData,
            });
            if (!response.ok) {
                var errorPayload;
                try {
                    errorPayload = await response.json();
                } catch (_error) {
                    errorPayload = {};
                }
                throw new Error(errorPayload.error || label("The article preview could not be rendered."));
            }
            var previewHtml = await response.text();
            state.previewFrame.onload = function () {
                window.requestAnimationFrame(function () {
                    var previewWindow = state.previewFrame.contentWindow;
                    var previewDocument = state.previewFrame.contentDocument;
                    if (!previewWindow || !previewDocument) {
                        return;
                    }
                    scrollPreviewToAnchor(
                        state,
                        activeAnchor ? activeAnchor.id : null,
                        ratio
                    );
                });
            };
            state.previewFrame.srcdoc = previewHtml;
            state.wrapper.hidden = true;
            state.previewFrame.hidden = false;
            state.previewVisible = true;
            setPreviewButtonState(state, true);
        } catch (error) {
            window.alert(error.message || label("The article preview could not be rendered."));
        } finally {
            state.previewButton.disabled = false;
            state.toolbar.classList.remove("is-busy");
        }
    }

    function toggleVisualPreview(state) {
        if (state.previewVisible) {
            showHtmlEditor(state);
            return;
        }
        showVisualPreview(state);
    }

    function clearFormatting(editor) {
        var selected = editor.getSelection();
        if (!selected) {
            window.alert(label("Select the HTML fragment whose formatting should be removed."));
            return;
        }
        var cleaned = selected
            .replace(/<\/?(?:strong|b|em|i|u|s|strike|del|mark|code)\b[^>]*>/gi, "")
            .replace(/<\/?h[2-6]\b[^>]*>/gi, "")
            .replace(/<\/?blockquote\b[^>]*>/gi, "");
        replaceSelection(editor, cleaned);
    }

    function formatHtml(editor, shouldFocus) {
        if (typeof window.html_beautify !== "function") {
            window.alert(label("HTML formatter is unavailable."));
            return false;
        }
        var cursorIndex = editor.indexFromPos(editor.getCursor());
        var scroll = editor.getScrollInfo();
        var formatted = window.html_beautify(editor.getValue(), {
            indent_size: 4,
            indent_char: " ",
            indent_inner_html: true,
            preserve_newlines: true,
            max_preserve_newlines: 2,
            wrap_line_length: 0,
            end_with_newline: false,
            extra_liners: [],
        });
        editor.operation(function () {
            editor.setValue(formatted);
            editor.setCursor(editor.posFromIndex(Math.min(cursorIndex, formatted.length)));
            editor.scrollTo(scroll.left, scroll.top);
        });
        if (shouldFocus !== false) {
            editor.focus();
        }
        return true;
    }

    async function editWithAi(state, button) {
        var editor = state.editor;
        var selectedText = editor.getSelection();
        if (!selectedText.trim()) {
            window.alert(label("Select the text you want to edit with AI."));
            return;
        }
        var instruction = window.prompt(
            label("Describe how to change the selected text. Specify language, tone and desired length if needed.")
        );
        if (!instruction || !instruction.trim()) {
            return;
        }
        if (!state.textarea.dataset.aiEditUrl) {
            window.alert(label("AI text editing URL is not configured."));
            return;
        }

        var from = editor.getCursor("from");
        var to = editor.getCursor("to");
        var formData = new FormData();
        formData.append("selected_text", selectedText);
        formData.append("text_prompt", instruction.trim());
        button.disabled = true;
        state.toolbar.classList.add("is-busy");
        editor.setOption("readOnly", "nocursor");
        try {
            var response = await window.fetch(state.textarea.dataset.aiEditUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: formData,
            });
            var payload = await response.json();
            if (!response.ok || !payload.text) {
                throw new Error(payload.error || label("AI text editing failed."));
            }
            var startIndex = editor.indexFromPos(from);
            editor.replaceRange(payload.text, from, to, "+ai-edit");
            editor.setSelection(from, editor.posFromIndex(startIndex + payload.text.length));
            editor.save();
        } catch (error) {
            window.alert(error.message || label("AI text editing failed."));
        } finally {
            editor.setOption("readOnly", false);
            state.toolbar.classList.remove("is-busy");
            button.disabled = false;
            editor.focus();
        }
    }

    function buildToolbar(state) {
        var editor = state.editor;
        var toolbar = document.createElement("div");
        toolbar.className = "article-code-toolbar";
        toolbar.setAttribute("aria-label", label("Article HTML tools"));
        state.toolbar = toolbar;

        var main = createGroup(toolbar, "Content tools");
        var imagesButton = createButton("imagesmode", "Images", function () {
            document.dispatchEvent(new CustomEvent("wulver:open-article-images", {
                detail: {inputName: state.textarea.name},
            }));
        });
        imagesButton.classList.add("is-primary");
        main.appendChild(imagesButton);
        state.previewButton = createButton("visibility", "Visual preview", function () {
            toggleVisualPreview(state);
        });
        state.previewButton.classList.add("is-preview");
        main.appendChild(state.previewButton);
        var aiButton = createButton("auto_awesome", "Edit selected text with AI", function () {
            editWithAi(state, aiButton);
        });
        aiButton.classList.add("is-ai");
        main.appendChild(aiButton);
        main.appendChild(createButton("css", "CSS classes", function () {
            openCssClassPicker(state);
        }));

        var inline = createGroup(toolbar, "Inline formatting");
        inline.appendChild(createButton("format_bold", "Bold", function () {
            wrapSelection(editor, "<strong>", "</strong>");
        }));
        inline.appendChild(createButton("format_italic", "Italic", function () {
            wrapSelection(editor, "<em>", "</em>");
        }));
        inline.appendChild(createButton("format_underlined", "Underline", function () {
            wrapSelection(editor, "<u>", "</u>");
        }));
        inline.appendChild(createButton("format_strikethrough", "Strikethrough", function () {
            wrapSelection(editor, "<s>", "</s>");
        }));
        inline.appendChild(createButton("code", "Code", function () {
            insertCode(editor);
        }));
        inline.appendChild(createButton("link", "Link", function () {
            insertLink(editor);
        }));
        inline.appendChild(createButton("add_link", "Site links", function () {
            openSiteLinks(state);
        }));

        var headings = createGroup(toolbar, "Headings");
        [2, 3, 4, 5, 6].forEach(function (level) {
            headings.appendChild(createButton("format_h" + level, "Heading " + level, function () {
                wrapBlock(editor, "h" + level, "", label("Heading"));
            }));
        });

        var blocks = createGroup(toolbar, "Block formatting");
        blocks.appendChild(createButton("format_align_center", "Align center", function () {
            wrapBlock(editor, "div", 'style="text-align: center;"');
        }));
        blocks.appendChild(createButton("format_quote", "Block quote", function () {
            wrapBlock(editor, "blockquote", "");
        }));
        blocks.appendChild(createButton("format_list_bulleted", "Unordered list", function () {
            insertList(editor, false);
        }));
        blocks.appendChild(createButton("format_list_numbered", "Ordered list", function () {
            insertList(editor, true);
        }));
        blocks.appendChild(createButton("format_indent_increase", "Indent right", function () {
            wrapBlock(editor, "div", 'style="margin-left: 2rem;"');
        }));
        blocks.appendChild(createButton("format_clear", "Clear formatting", function () {
            clearFormatting(editor);
        }));

        var tools = createGroup(toolbar, "Code tools");
        tools.appendChild(createButton("format_align_left", "Format HTML", function () {
            formatHtml(editor);
        }));
        state.wrapper.parentNode.insertBefore(toolbar, state.wrapper);
    }

    function refreshWhenVisible(state) {
        if (!state || state.refreshScheduled || !isVisible(state.wrapper)) {
            return;
        }
        state.refreshScheduled = true;
        window.requestAnimationFrame(function () {
            state.refreshScheduled = false;
            if (isVisible(state.wrapper)) {
                state.editor.refresh();
            }
        });
    }

    function initializeTextarea(textarea) {
        if (textarea.dataset.articleCodeEditorReady === "true") {
            return;
        }
        textarea.dataset.articleCodeEditorReady = "true";
        var editor = window.CodeMirror.fromTextArea(textarea, {
            mode: "htmlmixed",
            theme: "material-darker",
            lineNumbers: true,
            lineWrapping: true,
            indentUnit: 4,
            tabSize: 4,
            matchBrackets: true,
            autoCloseBrackets: true,
        });
        editor.setSize("100%", "36rem");
        var state = {
            textarea: textarea,
            editor: editor,
            wrapper: editor.getWrapperElement(),
            toolbar: null,
            previewButton: null,
            previewFrame: null,
            previewVisible: false,
            previewAnchors: [],
            refreshScheduled: false,
            observer: null,
        };
        state.previewFrame = document.createElement("iframe");
        state.previewFrame.className = "article-body-preview";
        state.previewFrame.title = label("Article body visual preview");
        state.previewFrame.hidden = true;
        state.wrapper.parentNode.insertBefore(state.previewFrame, state.wrapper.nextSibling);
        editors.push(state);
        buildToolbar(state);
        textarea._wulverCodeMirror = editor;
        document.dispatchEvent(new CustomEvent("wulver:code-editor-ready", {
            detail: {textarea: textarea, editor: editor},
        }));

        var form = textarea.closest("form");
        if (form) {
            form.addEventListener("submit", function () {
                formatHtml(editor, false);
                editor.save();
            }, true);
        }
        if (typeof window.ResizeObserver === "function") {
            state.observer = new window.ResizeObserver(function () {
                refreshWhenVisible(state);
            });
            state.observer.observe(state.wrapper);
        }
        window.setTimeout(function () { refreshWhenVisible(state); }, 100);
        window.setTimeout(function () { refreshWhenVisible(state); }, 400);
    }

    document.addEventListener("wulver:insert-article-image", function (event) {
        var detail = event.detail || {};
        var insertionKey = [detail.inputName, detail.imageUrl, detail.html].join("|");
        var insertionTime = Date.now();
        if (
            insertionKey === lastImageInsertion.key
            && insertionTime - lastImageInsertion.time < 1000
        ) {
            return;
        }
        lastImageInsertion = {key: insertionKey, time: insertionTime};
        var state = editors.find(function (item) {
            return item.textarea.name === detail.inputName;
        });
        if (!state || !detail.html) {
            return;
        }
        state.editor.replaceSelection("\n" + detail.html + "\n", "end", "+article-image");
        state.editor.save();
        state.editor.focus();
    });

    document.addEventListener("DOMContentLoaded", function () {
        if (typeof window.CodeMirror === "undefined") {
            return;
        }
        document.querySelectorAll("textarea.codemirror-article-body").forEach(
            initializeTextarea
        );
        document.addEventListener("click", function () {
            window.setTimeout(function () {
                editors.forEach(refreshWhenVisible);
            }, 0);
        });
    });
})();
