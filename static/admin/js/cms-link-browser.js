(function () {
    "use strict";

    function translate(message) {
        return typeof window.gettext === "function" ? window.gettext(message) : message;
    }

    function escapeAttribute(value) {
        return String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
    }

    function escapeHtml(value) {
        var element = document.createElement("div");
        element.textContent = String(value);
        return element.innerHTML;
    }

    function updateAnchorOpeningTag(openingTag, href, reference) {
        var result = openingTag;
        var hrefPattern = /\s+href\s*=\s*(["'])[\s\S]*?\1/i;
        var referencePattern = /\s+data-cms-link\s*=\s*(["'])[\s\S]*?\1/i;
        var hrefAttribute = ' href="' + escapeAttribute(href) + '"';
        var referenceAttribute = reference
            ? ' data-cms-link="' + escapeAttribute(reference) + '"'
            : "";

        result = hrefPattern.test(result)
            ? result.replace(hrefPattern, hrefAttribute)
            : result.replace(/>\s*$/, hrefAttribute + ">");
        if (reference) {
            result = referencePattern.test(result)
                ? result.replace(referencePattern, referenceAttribute)
                : result.replace(/>\s*$/, referenceAttribute + ">");
        }
        return result;
    }

    function applyItem(options, item) {
        var editor = options.editor;
        var selectedCode = editor.getSelection();
        var value = item[options.valueKey || "url_tag"];
        var reference = options.includeReference ? item.reference : "";
        var anchorMatch = selectedCode.match(
            /^([\s\S]*?<a\b[^>]*>)([\s\S]*?)(<\/a>[\s\S]*)$/i
        );
        var replacement;

        if (anchorMatch) {
            replacement = updateAnchorOpeningTag(anchorMatch[1], value, reference)
                + anchorMatch[2] + anchorMatch[3];
        } else if (selectedCode.trim()) {
            replacement = '<a href="' + escapeAttribute(value) + '"'
                + (reference ? ' data-cms-link="' + escapeAttribute(reference) + '"' : "")
                + ">" + selectedCode + "</a>";
        } else if (options.insertAnchorWithoutSelection) {
            replacement = '<a href="' + escapeAttribute(value) + '"'
                + (reference ? ' data-cms-link="' + escapeAttribute(reference) + '"' : "")
                + ">" + escapeHtml(item.title || value) + "</a>";
        } else {
            replacement = value;
        }

        editor.replaceSelection(replacement);
        if (typeof editor.save === "function") {
            editor.save();
        }
        editor.focus();
        if (typeof editor.refresh === "function") {
            editor.refresh();
        }
    }

    function createBackdrop(title) {
        var backdrop = document.createElement("div");
        var modal = document.createElement("div");
        var header = document.createElement("div");
        var heading = document.createElement("div");
        var closeButton = document.createElement("button");

        backdrop.className = "template-code-modal-backdrop";
        modal.className = "template-code-modal";
        header.className = "template-code-modal-header";
        heading.className = "template-code-modal-title";
        heading.textContent = translate(title);
        closeButton.type = "button";
        closeButton.className = "template-code-modal-close";
        closeButton.textContent = translate("Close");
        header.appendChild(heading);
        header.appendChild(closeButton);
        modal.appendChild(header);
        backdrop.appendChild(modal);
        return {backdrop: backdrop, modal: modal, closeButton: closeButton};
    }

    function openObjectModal(options, contentType, title) {
        var parts = createBackdrop(title);
        var controls = document.createElement("div");
        var searchInput = document.createElement("input");
        var status = document.createElement("span");
        var list = document.createElement("div");
        var loadMoreButton = document.createElement("button");
        var currentPage = 1;
        var searchTimer = null;
        var activeRequest = null;

        parts.modal.classList.add("template-code-cms-link-modal");
        controls.className = "template-code-cms-link-controls";
        searchInput.type = "search";
        searchInput.className = "template-code-cms-link-search";
        searchInput.placeholder = translate("Search by title or slug...");
        status.className = "template-code-cms-link-status";
        list.className = "template-code-modal-list template-code-cms-link-list";
        loadMoreButton.type = "button";
        loadMoreButton.className = "template-code-modal-option template-code-cms-link-more";
        loadMoreButton.textContent = translate("Load more");
        loadMoreButton.hidden = true;

        function closeModal() {
            if (activeRequest) {
                activeRequest.abort();
            }
            parts.backdrop.remove();
            options.editor.focus();
        }

        function createOption(item) {
            var option = document.createElement("button");
            var itemLabel = document.createElement("strong");
            var details = document.createElement("span");
            option.type = "button";
            option.className = "template-code-modal-option";
            itemLabel.textContent = item.title;
            details.textContent = item.category ? item.category + " / " + item.slug : item.slug;
            option.appendChild(itemLabel);
            option.appendChild(details);
            option.addEventListener("click", function () {
                applyItem(options, item);
                closeModal();
            });
            return option;
        }

        function loadItems(reset) {
            var params;
            if (activeRequest) {
                activeRequest.abort();
            }
            if (reset) {
                currentPage = 1;
                list.replaceChildren();
            }
            activeRequest = new AbortController();
            status.textContent = translate("Loading...");
            loadMoreButton.hidden = true;
            params = new URLSearchParams({
                type: contentType,
                q: searchInput.value.trim(),
                page: String(currentPage),
            });
            if (options.language) {
                params.set("language", options.language);
            }
            window.fetch(options.endpoint + "?" + params.toString(), {
                headers: {"X-Requested-With": "XMLHttpRequest"},
                signal: activeRequest.signal,
            }).then(function (response) {
                return response.json().then(function (data) {
                    return {response: response, data: data};
                });
            }).then(function (result) {
                if (!result.response.ok) {
                    throw new Error(result.data.error || translate("Could not load CMS links."));
                }
                result.data.items.forEach(function (item) {
                    list.appendChild(createOption(item));
                });
                status.textContent = list.children.length
                    ? list.children.length + " " + translate("loaded")
                    : translate("No matching items");
                loadMoreButton.hidden = !result.data.has_more;
            }).catch(function (error) {
                if (error.name !== "AbortError") {
                    status.textContent = error.message || translate("Could not load CMS links.");
                }
            });
        }

        parts.closeButton.addEventListener("click", closeModal);
        parts.backdrop.addEventListener("click", function (event) {
            if (event.target === parts.backdrop) {
                closeModal();
            }
        });
        searchInput.addEventListener("input", function () {
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(function () { loadItems(true); }, 250);
        });
        searchInput.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeModal();
            }
        });
        loadMoreButton.addEventListener("click", function () {
            currentPage += 1;
            loadItems(false);
        });
        controls.appendChild(searchInput);
        controls.appendChild(status);
        parts.modal.appendChild(controls);
        parts.modal.appendChild(list);
        parts.modal.appendChild(loadMoreButton);
        document.body.appendChild(parts.backdrop);
        loadItems(true);
        searchInput.focus();
    }

    function open(options) {
        var parts;
        var list;
        var types = [
            {type: "home", title: "Home"},
            {type: "page", title: "Page"},
            {type: "category", title: "Blog category"},
            {type: "article", title: "Article"},
        ];

        if (!options || !options.endpoint || !options.editor) {
            window.alert(translate("CMS link browser is not available."));
            return;
        }
        parts = createBackdrop("Choose CMS link type");
        list = document.createElement("div");
        list.className = "template-code-modal-list";
        types.forEach(function (item) {
            var option = document.createElement("button");
            option.type = "button";
            option.className = "template-code-modal-option";
            option.textContent = translate(item.title);
            option.addEventListener("click", function () {
                parts.backdrop.remove();
                if (item.type === "home") {
                    window.fetch(options.endpoint + "?" + new URLSearchParams({
                        type: "home",
                        language: options.language || "",
                    }).toString(), {
                        headers: {"X-Requested-With": "XMLHttpRequest"},
                    }).then(function (response) { return response.json(); })
                        .then(function (data) { applyItem(options, data.items[0]); })
                        .catch(function () {
                            window.alert(translate("Could not load CMS links."));
                        });
                    return;
                }
                openObjectModal(options, item.type, "Choose " + item.title.toLowerCase());
            });
            list.appendChild(option);
        });
        parts.closeButton.addEventListener("click", function () { parts.backdrop.remove(); });
        parts.backdrop.addEventListener("click", function (event) {
            if (event.target === parts.backdrop) {
                parts.backdrop.remove();
            }
        });
        parts.modal.appendChild(list);
        document.body.appendChild(parts.backdrop);
    }

    window.WulverCmsLinkBrowser = {open: open};
})();
