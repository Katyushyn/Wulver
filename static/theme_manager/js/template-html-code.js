document.addEventListener("DOMContentLoaded", function () {
    function translate(message) {
        return typeof message === "string" && typeof window.gettext === "function"
            ? window.gettext(message)
            : message;
    }

    const alert = function (message) {
        window.alert(translate(message));
    };
    const confirm = function (message) {
        return window.confirm(translate(message));
    };

    const textarea = document.querySelector(".codemirror-template-html");

    if (!textarea || typeof CodeMirror === "undefined") {
        return;
    }

    const toolbarGroups = {
        "Source HTML Files": {
            label: "Files",
            icon: "folder_open",
            description: "Load a source HTML file or insert its code at the cursor.",
        },
        "Django Template Tags": {
            label: "Django",
            icon: "data_object",
            description: "Insert common Django template tags at the current cursor position.",
        },
        "Site Settings Links": {
            label: "Site links",
            icon: "link",
            description: "Select a complete <a> tag, then connect it to contact or social settings.",
        },
        "Template Actions": {
            label: "Template",
            icon: "construction",
            description: "Convert, validate, extract, or insert reusable template structures.",
        },
        "Version History": {
            label: "History",
            icon: "history",
            description: "Compare the current editor with earlier saved versions and restore one safely.",
        },
        "AI Template Builder": {
            label: "AI",
            icon: "auto_awesome",
            description: "Select the relevant code or text before running an AI transformation.",
        },
    };

    const toolbarButtons = {
        "Load file": ["file_open", "Replace the editor content with a selected source HTML file."],
        "Insert file": ["note_add", "Insert a selected source HTML file at the cursor."],
        "Asset browser": ["photo_library", "Browse static and media images, preview them, and insert the correct path."],
        "Extends": ["vertical_align_top", "Choose a Base Template and insert a Django extends tag."],
        "Load static": ["download", "Insert {% load static %}."],
        "Load i18n": ["translate", "Insert {% load i18n %}."],
        "Load compress": ["compress", "Insert {% load compress %}."],
        "Load comments": ["comment", "Insert {% load comments %}."],
        "Current language": ["language", "Insert the current Django language variable."],
        "Language BIDI": ["format_textdirection_r_to_l", "Insert the current language direction variable."],
        "Variable": ["data_object", "Insert a Django template variable."],
        "URL": ["route", "Insert a Django {% url %} tag."],
        "Trans": ["translate", "Insert a Django {% trans %} tag."],
        "If": ["account_tree", "Insert an if block around the cursor."],
        "For": ["repeat", "Insert a for loop around the cursor."],
        "Email": ["mail", "Select a complete <a> tag. Replace its URL and text with the site email."],
        "Phone": ["call", "Select a complete <a> tag. Replace its URL and text with the site phone."],
        "X": ["alternate_email", "Select a complete <a> tag. Replace only its URL with the X profile."],
        "Facebook": ["public", "Select a complete <a> tag. Replace only its URL with the Facebook profile."],
        "Instagram": ["photo_camera", "Select a complete <a> tag. Replace only its URL with the Instagram profile."],
        "LinkedIn": ["work", "Select a complete <a> tag. Replace only its URL with the LinkedIn profile."],
        "YouTube": ["smart_display", "Select a complete <a> tag. Replace only its URL with the YouTube channel."],
        "TikTok": ["music_note", "Select a complete <a> tag. Replace only its URL with the TikTok profile."],
        "Telegram": ["send", "Select a complete <a> tag. Replace only its URL with the Telegram profile."],
        "WhatsApp": ["chat", "Select a complete <a> tag. Replace only its URL with the WhatsApp link."],
        "Replace static files": ["sync_alt", "Convert local asset paths in the template to Django static tags."],
        "Search & replace": ["find_replace", "Find text or regular expressions, navigate matches, and replace one or all."],
        "Template components": ["view_cozy", "Open a library of ready Django template blocks and insert one into the editor."],
        "Format": ["format_align_left", "Align HTML and Django template blocks using four-space indentation."],
        "Normalize SEO head": ["manage_search", "Add or normalize the editable SEO block inside <head>."],
        "Check template loads": ["fact_check", "Validate HTML tags, Django syntax, load libraries, static/media URLs, and duplicate IDs."],
        "Extract include": ["content_cut", "Select code and move it into a reusable include template."],
        "Add include": ["add_box", "Insert an existing include template at the cursor."],
        "Extract page block": ["splitscreen", "Select code and move it into a new child page template."],
        "Add page block": ["dashboard_customize", "Insert an empty Django page block at the cursor."],
        "Version history": ["history", "Open saved template versions, compare changes, or restore an earlier version."],
        "Generate image": ["image", "Select an image path, static tag, or <img>. Generate an AVIF and replace it with a media URL."],
        "Generate text": ["edit_note", "Select text, describe the desired result, and replace the selection."],
        "Generate HTML": ["code_blocks", "Select HTML or Django template code, describe the change, and replace the selection with AI-edited code."],
        "Add AI assistant": ["smart_toy", "Insert the reusable AI assistant chat widget include."],
        "Convert language switcher": ["language", "Select a language switcher and add working Django language URLs."],
        "Convert Breadcrumbs": ["conversion_path", "Select breadcrumb HTML and convert it to a dynamic Django breadcrumb while preserving layout."],
        "Convert Pagination": ["keyboard_double_arrow_right", "Select pagination HTML and convert it to page_obj-based Django pagination while preserving layout."],
        "Convert Subscription": ["mark_email_read", "Select subscription HTML and connect it to the CMS subscription endpoint while preserving layout."],
        "Convert Contact form": ["contact_mail", "Select contact form HTML and connect it to the CMS message endpoint while preserving layout."],
        "Convert Comments": ["comment", "Select comments HTML and convert it to django-comments markup while preserving layout."],
        "Convert to latest blog articles": ["dynamic_feed", "Select an article/card/list block and convert it to latest_blog_articles while preserving layout."],
        "Add translations": ["g_translate", "Select code and wrap translatable text in Django translation tags."],
        "Language switcher": ["translate", "Insert a default working Django language switcher."],
    };

    let templateComponents = null;
    let templateComponentsRequest = null;

    function getCookie(name) {
        const cookies = document.cookie.split(";");

        for (let cookie of cookies) {
            cookie = cookie.trim();

            if (cookie.startsWith(name + "=")) {
                return decodeURIComponent(cookie.substring(name.length + 1));
            }
        }

        return null;
    }

    function createButton(label, onClick) {
        const button = document.createElement("button");
        const metadata = toolbarButtons[label] || ["bolt", label];
        button.type = "button";
        button.className = "template-code-toolbar-button";
        button.dataset.tooltip = translate(metadata[1]);
        button.setAttribute("aria-label", translate(label) + ". " + translate(metadata[1]));

        const icon = document.createElement("span");
        icon.className = "material-symbols-outlined template-code-toolbar-button-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = metadata[0];

        const text = document.createElement("span");
        text.className = "template-code-toolbar-button-label";
        text.textContent = translate(label);

        button.appendChild(icon);
        button.appendChild(text);
        button.addEventListener("click", function (event) {
            runEditorAction(onClick, event);
        });

        return button;
    }

    function createGroup(title) {
        const metadata = toolbarGroups[title] || {
            label: title,
            icon: "widgets",
            description: "",
        };
        const group = document.createElement("div");
        group.className = "template-code-toolbar-group";
        group.dataset.tabLabel = translate(metadata.label);
        group.dataset.tabIcon = metadata.icon;
        group.dataset.description = translate(metadata.description);
        group.dataset.groupTitle = title;

        const label = document.createElement("div");
        label.className = "template-code-toolbar-title";
        label.textContent = translate(title);

        const actions = document.createElement("div");
        actions.className = "template-code-toolbar-actions";

        group.appendChild(label);
        group.appendChild(actions);

        return {
            group: group,
            actions: actions,
        };
    }

    function activateToolbarTab(toolbar, tabButton) {
        const tabButtons = toolbar.querySelectorAll(".template-code-toolbar-tab");
        const panels = toolbar.querySelectorAll(".template-code-toolbar-group");
        const description = toolbar.querySelector(".template-code-toolbar-description");
        const panelId = tabButton.getAttribute("aria-controls");

        tabButtons.forEach(function (button) {
            const isActive = button === tabButton;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-selected", isActive ? "true" : "false");
            button.tabIndex = isActive ? 0 : -1;
        });

        panels.forEach(function (panel) {
            const isActive = panel.id === panelId;
            panel.classList.toggle("is-active", isActive);
            panel.hidden = !isActive;
        });

        const activePanel = document.getElementById(panelId);
        description.textContent = activePanel ? activePanel.dataset.description : "";
    }

    function buildToolbarTabs(toolbar) {
        const groups = Array.from(
            toolbar.querySelectorAll(".template-code-toolbar-group")
        );
        const header = document.createElement("div");
        const tabs = document.createElement("div");
        const controls = document.createElement("div");
        const description = document.createElement("div");
        const panels = document.createElement("div");

        header.className = "template-code-toolbar-header";
        tabs.className = "template-code-toolbar-tabs";
        tabs.setAttribute("role", "tablist");
        tabs.setAttribute("aria-label", translate("Template editor tools"));
        controls.className = "template-code-toolbar-controls";
        description.className = "template-code-toolbar-description";
        description.setAttribute("aria-live", "polite");
        panels.className = "template-code-toolbar-panels";

        groups.forEach(function (group, index) {
            const panelId = "template-code-toolbar-panel-" + index;
            const tabId = "template-code-toolbar-tab-" + index;
            const tab = document.createElement("button");
            const icon = document.createElement("span");
            const label = document.createElement("span");

            group.id = panelId;
            group.setAttribute("role", "tabpanel");
            group.setAttribute("aria-labelledby", tabId);

            tab.type = "button";
            tab.id = tabId;
            tab.className = "template-code-toolbar-tab";
            tab.setAttribute("role", "tab");
            tab.setAttribute("aria-controls", panelId);
            tab.setAttribute("aria-selected", "false");

            icon.className = "material-symbols-outlined template-code-toolbar-tab-icon";
            icon.setAttribute("aria-hidden", "true");
            icon.textContent = group.dataset.tabIcon;
            label.textContent = translate(group.dataset.tabLabel);

            tab.appendChild(icon);
            tab.appendChild(label);
            tab.addEventListener("click", function () {
                activateToolbarTab(toolbar, tab);
            });
            tab.addEventListener("keydown", function (event) {
                if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
                    return;
                }

                event.preventDefault();
                const tabButtons = Array.from(
                    tabs.querySelectorAll(".template-code-toolbar-tab")
                );
                const currentIndex = tabButtons.indexOf(tab);
                let nextIndex = currentIndex;

                if (event.key === "ArrowLeft") {
                    nextIndex = (currentIndex - 1 + tabButtons.length) % tabButtons.length;
                } else if (event.key === "ArrowRight") {
                    nextIndex = (currentIndex + 1) % tabButtons.length;
                } else if (event.key === "Home") {
                    nextIndex = 0;
                } else if (event.key === "End") {
                    nextIndex = tabButtons.length - 1;
                }

                activateToolbarTab(toolbar, tabButtons[nextIndex]);
                tabButtons[nextIndex].focus();
            });

            tabs.appendChild(tab);
            panels.appendChild(group);
        });

        header.appendChild(tabs);
        header.appendChild(controls);
        toolbar.replaceChildren(header, description, panels);
        if (tabs.firstElementChild) {
            activateToolbarTab(toolbar, tabs.firstElementChild);
        }
    }

    function createFullscreenToggle(editorShell, toolbar, editor) {
        const controls = toolbar.querySelector(".template-code-toolbar-controls");
        const fullscreenStorageKey = "wulver-template-editor-fullscreen:" + window.location.pathname;

        if (!controls) {
            return;
        }

        const saveButton = document.createElement("button");
        const saveIcon = document.createElement("span");
        const saveLabel = document.createElement("span");
        const button = document.createElement("button");
        const icon = document.createElement("span");

        saveButton.type = "submit";
        saveButton.name = "_continue";
        saveButton.value = "Save and continue editing";
        saveButton.className = "template-code-toolbar-save-button";
        saveButton.setAttribute("aria-label", "Save and continue editing");
        saveButton.hidden = true;

        saveIcon.className = "material-symbols-outlined";
        saveIcon.setAttribute("aria-hidden", "true");
        saveIcon.textContent = "save";
        saveLabel.textContent = translate("Save and continue editing");
        saveButton.appendChild(saveIcon);
        saveButton.appendChild(saveLabel);
        saveButton.addEventListener("click", function () {
            editor.save();
        });

        button.type = "button";
        button.className = "template-code-toolbar-icon-button";
        button.setAttribute("aria-pressed", "false");
        button.dataset.tooltip = "Expand editor";

        icon.className = "material-symbols-outlined";
        icon.setAttribute("aria-hidden", "true");
        button.appendChild(icon);

        function refreshEditor() {
            window.setTimeout(function () {
                editor.refresh();
            }, 0);
        }

        function setFullscreen(isFullscreen) {
            editorShell.classList.toggle("is-fullscreen", isFullscreen);
            toolbar.classList.toggle("is-fullscreen", isFullscreen);
            document.body.classList.toggle("template-code-editor-fullscreen-open", isFullscreen);
            button.setAttribute("aria-pressed", isFullscreen ? "true" : "false");
            button.setAttribute("aria-label", isFullscreen ? "Collapse editor" : "Expand editor");
            button.dataset.tooltip = isFullscreen ? "Collapse editor" : "Expand editor";
            icon.textContent = isFullscreen ? "close_fullscreen" : "open_in_full";
            saveButton.hidden = !isFullscreen;

            try {
                if (isFullscreen) {
                    window.sessionStorage.setItem(fullscreenStorageKey, "1");
                } else {
                    window.sessionStorage.removeItem(fullscreenStorageKey);
                }
            } catch (error) {
                // The editor still works when browser storage is unavailable.
            }

            refreshEditor();
        }

        button.addEventListener("click", function () {
            setFullscreen(!editorShell.classList.contains("is-fullscreen"));
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && editorShell.classList.contains("is-fullscreen")) {
                setFullscreen(false);
                button.focus();
            }
        });

        controls.appendChild(saveButton);
        controls.appendChild(button);

        let restoreFullscreen = false;

        try {
            restoreFullscreen = window.sessionStorage.getItem(fullscreenStorageKey) === "1";
        } catch (error) {
            restoreFullscreen = false;
        }

        setFullscreen(restoreFullscreen);
    }

    function insertTag(tag) {
        editor.replaceSelection(tag + "\n");
        editor.focus();
        editor.refresh();
    }

    function createSearchReplacePanel() {
        const panel = document.createElement("div");
        const searchRow = document.createElement("div");
        const replaceRow = document.createElement("div");
        const searchInput = document.createElement("input");
        const replaceInput = document.createElement("input");
        const previousButton = document.createElement("button");
        const nextButton = document.createElement("button");
        const replaceButton = document.createElement("button");
        const replaceAllButton = document.createElement("button");
        const caseLabel = document.createElement("label");
        const caseCheckbox = document.createElement("input");
        const regexLabel = document.createElement("label");
        const regexCheckbox = document.createElement("input");
        const status = document.createElement("span");
        const closeButton = document.createElement("button");
        let matches = [];
        let activeIndex = -1;

        panel.className = "template-code-search-panel";
        panel.hidden = true;
        searchRow.className = "template-code-search-row";
        replaceRow.className = "template-code-search-row";
        searchInput.type = "text";
        searchInput.className = "template-code-search-input";
        searchInput.placeholder = "Find";
        searchInput.setAttribute("aria-label", "Find text");
        replaceInput.type = "text";
        replaceInput.className = "template-code-search-input";
        replaceInput.placeholder = "Replace with";
        replaceInput.setAttribute("aria-label", "Replacement text");

        function setIconButton(button, iconName, label) {
            button.type = "button";
            button.className = "template-code-search-icon-button";
            button.setAttribute("aria-label", label);
            button.title = label;
            button.innerHTML = (
                '<span class="material-symbols-outlined" aria-hidden="true">' +
                iconName +
                "</span>"
            );
        }

        setIconButton(previousButton, "keyboard_arrow_up", "Previous match");
        setIconButton(nextButton, "keyboard_arrow_down", "Next match");
        setIconButton(closeButton, "close", "Close search and replace");

        replaceButton.type = "button";
        replaceButton.className = "template-code-search-command";
        replaceButton.textContent = translate("Replace");
        replaceAllButton.type = "button";
        replaceAllButton.className = "template-code-search-command";
        replaceAllButton.textContent = translate("Replace all");

        caseCheckbox.type = "checkbox";
        caseCheckbox.className = "template-code-search-checkbox";
        caseLabel.className = "template-code-search-option";
        caseLabel.appendChild(caseCheckbox);
        caseLabel.appendChild(document.createTextNode("Match case"));

        regexCheckbox.type = "checkbox";
        regexCheckbox.className = "template-code-search-checkbox";
        regexLabel.className = "template-code-search-option";
        regexLabel.appendChild(regexCheckbox);
        regexLabel.appendChild(document.createTextNode("Regex"));

        status.className = "template-code-search-status";
        status.setAttribute("aria-live", "polite");

        function escapeRegExp(value) {
            return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        }

        function buildPattern(global) {
            const query = searchInput.value;
            if (!query) {
                return null;
            }
            const source = regexCheckbox.checked ? query : escapeRegExp(query);
            let flags = caseCheckbox.checked ? "" : "i";
            if (global) {
                flags += "g";
            }
            return new RegExp(source, flags);
        }

        function collectMatches() {
            matches = [];
            activeIndex = -1;
            status.classList.remove("is-error");

            if (!searchInput.value) {
                status.textContent = translate("Enter text to search");
                return;
            }

            let pattern;
            try {
                pattern = buildPattern(true);
            } catch (error) {
                status.textContent = translate("Invalid regex: " + error.message);
                status.classList.add("is-error");
                return;
            }

            const code = editor.getValue();
            let match = pattern.exec(code);
            while (match) {
                matches.push({
                    start: match.index,
                    end: match.index + match[0].length,
                    text: match[0],
                    groups: match,
                });
                if (match[0].length === 0) {
                    pattern.lastIndex += 1;
                }
                match = pattern.exec(code);
            }

            status.textContent = translate(matches.length
                ? matches.length + " matches"
                : "No matches");
        }

        function selectMatch(index) {
            if (!matches.length) {
                collectMatches();
            }
            if (!matches.length) {
                return;
            }

            activeIndex = (index + matches.length) % matches.length;
            const match = matches[activeIndex];
            const from = editor.posFromIndex(match.start);
            const to = editor.posFromIndex(match.end);
            editor.setSelection(from, to);
            editor.scrollIntoView({from: from, to: to}, 80);
            editor.focus();
            status.textContent = translate((
                (activeIndex + 1) + " of " + matches.length
            ));
        }

        function findFromCursor(direction) {
            collectMatches();
            if (!matches.length) {
                return;
            }
            const cursorIndex = editor.indexFromPos(
                editor.getCursor(direction > 0 ? "to" : "from")
            );
            let targetIndex;
            if (direction > 0) {
                targetIndex = matches.findIndex(function (match) {
                    return match.start >= cursorIndex;
                });
                if (targetIndex === -1) {
                    targetIndex = 0;
                }
            } else {
                targetIndex = matches.length - 1;
                for (let index = matches.length - 1; index >= 0; index -= 1) {
                    if (matches[index].end <= cursorIndex) {
                        targetIndex = index;
                        break;
                    }
                }
            }
            selectMatch(targetIndex);
        }

        function getReplacement(match) {
            if (!regexCheckbox.checked) {
                return replaceInput.value;
            }
            const pattern = buildPattern(false);
            return match.text.replace(pattern, replaceInput.value);
        }

        function replaceCurrent() {
            const selectionStart = editor.indexFromPos(editor.getCursor("from"));
            const selectionEnd = editor.indexFromPos(editor.getCursor("to"));
            collectMatches();
            activeIndex = matches.findIndex(function (match) {
                return match.start === selectionStart && match.end === selectionEnd;
            });

            if (activeIndex < 0) {
                findFromCursor(1);
            }
            if (activeIndex < 0 || !matches[activeIndex]) {
                return;
            }

            const match = matches[activeIndex];
            const replacementStart = match.start;
            editor.replaceRange(
                getReplacement(match),
                editor.posFromIndex(match.start),
                editor.posFromIndex(match.end)
            );
            collectMatches();
            if (matches.length) {
                let nextIndex = matches.findIndex(function (item) {
                    return item.start >= replacementStart;
                });
                if (nextIndex === -1) {
                    nextIndex = 0;
                }
                selectMatch(nextIndex);
            }
            editor.focus();
        }

        function replaceAll() {
            collectMatches();
            if (!matches.length) {
                return;
            }

            let pattern;
            try {
                pattern = buildPattern(true);
            } catch (error) {
                status.textContent = translate("Invalid regex: " + error.message);
                status.classList.add("is-error");
                return;
            }

            const count = matches.length;
            const replacement = replaceInput.value;
            const updated = regexCheckbox.checked
                ? editor.getValue().replace(pattern, replacement)
                : editor.getValue().replace(pattern, function () {
                    return replacement;
                });
            editor.operation(function () {
                editor.setValue(updated);
            });
            collectMatches();
            status.textContent = translate(count + " replacements made");
            editor.focus();
        }

        function resetSearch() {
            matches = [];
            activeIndex = -1;
            collectMatches();
        }

        searchInput.addEventListener("input", resetSearch);
        caseCheckbox.addEventListener("change", resetSearch);
        regexCheckbox.addEventListener("change", resetSearch);
        searchInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                findFromCursor(event.shiftKey ? -1 : 1);
            } else if (event.key === "Escape") {
                panel.hidden = true;
                editor.focus();
            }
        });
        replaceInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                replaceCurrent();
            } else if (event.key === "Escape") {
                panel.hidden = true;
                editor.focus();
            }
        });
        previousButton.addEventListener("click", function () {
            findFromCursor(-1);
        });
        nextButton.addEventListener("click", function () {
            findFromCursor(1);
        });
        replaceButton.addEventListener("click", replaceCurrent);
        replaceAllButton.addEventListener("click", replaceAll);
        closeButton.addEventListener("click", function () {
            panel.hidden = true;
            editor.focus();
        });

        searchRow.appendChild(searchInput);
        searchRow.appendChild(previousButton);
        searchRow.appendChild(nextButton);
        searchRow.appendChild(caseLabel);
        searchRow.appendChild(regexLabel);
        searchRow.appendChild(status);
        searchRow.appendChild(closeButton);
        replaceRow.appendChild(replaceInput);
        replaceRow.appendChild(replaceButton);
        replaceRow.appendChild(replaceAllButton);
        panel.appendChild(searchRow);
        panel.appendChild(replaceRow);

        return {
            element: panel,
            open: function () {
                panel.hidden = false;
                const selectedText = editor.getSelection();
                if (selectedText && !selectedText.includes("\n")) {
                    searchInput.value = selectedText;
                }
                collectMatches();
                searchInput.focus();
                searchInput.select();
            },
        };
    }

    function buildAnchorHref(value, prefix) {
        if (!prefix) {
            return value;
        }

        return prefix + value;
    }

    function replaceOrAddHref(openingTag, href) {
        const hrefPattern = /\s+href\s*=\s*(["'])[\s\S]*?\1/i;

        if (hrefPattern.test(openingTag)) {
            return openingTag.replace(hrefPattern, ' href="' + href + '"');
        }

        return openingTag.replace(/>\s*$/, ' href="' + href + '">');
    }

    function replaceSelectedAnchor(label, value, options) {
        const selectedCode = editor.getSelection();
        const match = selectedCode.match(/^([\s\S]*?<a\b[^>]*>)([\s\S]*?)(<\/a>[\s\S]*)$/i);

        if (!selectedCode.trim() || !match) {
            alert("Select one complete <a> tag first.");
            return;
        }

        const href = buildAnchorHref(value, options && options.prefix);
        const openingTag = replaceOrAddHref(match[1], href);
        const innerHtml = options && options.replaceText ? value : match[2];

        editor.replaceSelection(openingTag + innerHtml + match[3]);
        editor.focus();
        editor.refresh();
    }
    function openChoiceModal(title, items, getLabel, onSelect) {
        if (!items.length) {
            alert("No items found.");
            return;
        }

        const backdrop = document.createElement("div");
        backdrop.className = "template-code-modal-backdrop";

        const modal = document.createElement("div");
        modal.className = "template-code-modal";

        const header = document.createElement("div");
        header.className = "template-code-modal-header";

        const heading = document.createElement("div");
        heading.className = "template-code-modal-title";
        heading.textContent = translate(title);

        const closeButton = document.createElement("button");
        closeButton.type = "button";
        closeButton.className = "template-code-modal-close";
        closeButton.textContent = translate("Close");

        const list = document.createElement("div");
        list.className = "template-code-modal-list";

        function closeModal() {
            backdrop.remove();
        }

        items.forEach(function (item) {
            const option = document.createElement("button");
            option.type = "button";
            option.className = "template-code-modal-option";
            option.textContent = getLabel(item);
            option.addEventListener("click", function () {
                onSelect(item);
                closeModal();
            });
            list.appendChild(option);
        });

        closeButton.addEventListener("click", closeModal);
        backdrop.addEventListener("click", function (event) {
            if (event.target === backdrop) {
                closeModal();
            }
        });

        header.appendChild(heading);
        header.appendChild(closeButton);
        modal.appendChild(header);
        modal.appendChild(list);
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
    }

    function applyCmsLink(urlTag) {
        const selectedCode = editor.getSelection();
        const anchorMatch = selectedCode.match(
            /^([\s\S]*?<a\b[^>]*>)([\s\S]*?)(<\/a>[\s\S]*)$/i
        );

        if (anchorMatch) {
            editor.replaceSelection(
                replaceOrAddHref(anchorMatch[1], urlTag) +
                anchorMatch[2] +
                anchorMatch[3]
            );
        } else if (selectedCode.trim()) {
            editor.replaceSelection(
                '<a href="' + urlTag + '">' + selectedCode + "</a>"
            );
        } else {
            editor.replaceSelection(urlTag);
        }

        editor.focus();
        editor.refresh();
    }

    function openCmsLinkObjectModal(contentType, title) {
        if (!textarea.dataset.cmsLinkOptionsUrl) {
            alert("CMS link browser is not available.");
            return;
        }

        const backdrop = document.createElement("div");
        const modal = document.createElement("div");
        const header = document.createElement("div");
        const heading = document.createElement("div");
        const closeButton = document.createElement("button");
        const controls = document.createElement("div");
        const searchInput = document.createElement("input");
        const status = document.createElement("span");
        const list = document.createElement("div");
        const loadMoreButton = document.createElement("button");
        let currentPage = 1;
        let searchTimer = null;
        let activeRequest = null;

        backdrop.className = "template-code-modal-backdrop";
        modal.className = "template-code-modal template-code-cms-link-modal";
        header.className = "template-code-modal-header";
        heading.className = "template-code-modal-title";
        heading.textContent = translate(title);
        closeButton.type = "button";
        closeButton.className = "template-code-modal-close";
        closeButton.textContent = translate("Close");
        controls.className = "template-code-cms-link-controls";
        searchInput.type = "search";
        searchInput.className = "template-code-cms-link-search";
        searchInput.placeholder = "Search by title or slug...";
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
            backdrop.remove();
            editor.focus();
        }

        function createOption(item) {
            const option = document.createElement("button");
            const label = document.createElement("strong");
            const details = document.createElement("span");
            option.type = "button";
            option.className = "template-code-modal-option";
            label.textContent = translate(item.title);
            details.textContent = item.category
                ? item.category + " / " + item.slug
                : item.slug;
            option.appendChild(label);
            option.appendChild(details);
            option.addEventListener("click", function () {
                applyCmsLink(item.url_tag);
                closeModal();
            });
            return option;
        }

        function loadItems(reset) {
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
            const params = new URLSearchParams({
                type: contentType,
                q: searchInput.value.trim(),
                page: String(currentPage),
            });

            editorFetch(textarea.dataset.cmsLinkOptionsUrl + "?" + params.toString(), {
                headers: {"X-Requested-With": "XMLHttpRequest"},
                signal: activeRequest.signal,
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return {response: response, data: data};
                    });
                })
                .then(function (result) {
                    if (!result.response.ok) {
                        throw new Error(result.data.error || "Could not load CMS links.");
                    }
                    result.data.items.forEach(function (item) {
                        list.appendChild(createOption(item));
                    });
                    status.textContent = translate(list.children.length
                        ? list.children.length + " loaded"
                        : "No matching items");
                    loadMoreButton.hidden = !result.data.has_more;
                })
                .catch(function (error) {
                    if (error.name === "AbortError") {
                        return;
                    }
                    console.error(error);
                    status.textContent = translate(error.message || "Could not load CMS links.");
                });
        }

        closeButton.addEventListener("click", closeModal);
        backdrop.addEventListener("click", function (event) {
            if (event.target === backdrop) {
                closeModal();
            }
        });
        searchInput.addEventListener("input", function () {
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(function () {
                loadItems(true);
            }, 250);
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

        header.appendChild(heading);
        header.appendChild(closeButton);
        controls.appendChild(searchInput);
        controls.appendChild(status);
        modal.appendChild(header);
        modal.appendChild(controls);
        modal.appendChild(list);
        modal.appendChild(loadMoreButton);
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
        loadItems(true);
        searchInput.focus();
    }

    function openCmsLinkModal() {
        if (!window.WulverCmsLinkBrowser) {
            alert("CMS link browser is not available.");
            return;
        }
        window.WulverCmsLinkBrowser.open({
            endpoint: textarea.dataset.cmsLinkOptionsUrl,
            editor: editor,
            valueKey: "url_tag",
            insertAnchorWithoutSelection: false,
            includeReference: false,
        });
    }

    function openBlogCategoryChildrenModal() {
        const selectedCode = editor.getSelection();

        if (!selectedCode.trim()) {
            alert("Select the list or navigation HTML you want to convert.");
            return;
        }
        if (!textarea.dataset.blogCategoryTreeUrl) {
            alert("Blog category tree is not available.");
            return;
        }

        const backdrop = document.createElement("div");
        const modal = document.createElement("div");
        const header = document.createElement("div");
        const heading = document.createElement("div");
        const closeButton = document.createElement("button");
        const controls = document.createElement("div");
        const searchInput = document.createElement("input");
        const status = document.createElement("span");
        const list = document.createElement("div");
        let categories = [];

        backdrop.className = "template-code-modal-backdrop";
        modal.className = "template-code-modal template-code-category-tree-modal";
        header.className = "template-code-modal-header";
        heading.className = "template-code-modal-title";
        heading.textContent = translate("Choose parent blog category");
        closeButton.type = "button";
        closeButton.className = "template-code-modal-close";
        closeButton.textContent = translate("Close");
        controls.className = "template-code-cms-link-controls";
        searchInput.type = "search";
        searchInput.className = "template-code-cms-link-search";
        searchInput.placeholder = "Search category...";
        status.className = "template-code-cms-link-status";
        list.className = "template-code-modal-list template-code-category-tree-list";

        function closeModal() {
            backdrop.remove();
            editor.focus();
        }

        function categoryMatches(category, query) {
            if (!query) {
                return true;
            }

            return (
                category.title.toLowerCase().includes(query)
                || category.slug.toLowerCase().includes(query)
            );
        }

        function renderCategories() {
            const query = searchInput.value.trim().toLowerCase();
            const filtered = categories.filter(function (category) {
                return categoryMatches(category, query);
            });

            list.replaceChildren();
            filtered.forEach(function (category) {
                const option = document.createElement("button");
                const title = document.createElement("strong");
                const details = document.createElement("span");
                const marker = document.createElement("span");

                option.type = "button";
                option.className = "template-code-modal-option template-code-category-tree-option";
                option.style.setProperty("--category-depth", String(category.depth || 0));
                marker.className = "template-code-category-tree-marker";
                marker.textContent = category.child_count ? "subdirectory_arrow_right" : "label";
                title.textContent = category.title;
                details.textContent = category.slug + " / " + category.child_count + " direct children";

                option.appendChild(marker);
                option.appendChild(title);
                option.appendChild(details);
                option.addEventListener("click", function () {
                    const categoryInstruction = window.prompt(
                        "Additional instruction for this category list conversion:",
                        ""
                    );

                    if (categoryInstruction === null) {
                        return;
                    }

                    closeModal();
                    runAiAction("convert_component", {
                        component_type: "blog_category_children",
                        category_id: category.id,
                        category_title: category.title,
                        category_slug: category.slug,
                        category_instruction: categoryInstruction.trim(),
                    });
                });
                list.appendChild(option);
            });
            status.textContent = translate(filtered.length
                ? filtered.length + " categories"
                : "No matching categories");
        }

        closeButton.addEventListener("click", closeModal);
        backdrop.addEventListener("click", function (event) {
            if (event.target === backdrop) {
                closeModal();
            }
        });
        searchInput.addEventListener("input", renderCategories);
        searchInput.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeModal();
            }
        });

        header.appendChild(heading);
        header.appendChild(closeButton);
        controls.appendChild(searchInput);
        controls.appendChild(status);
        modal.appendChild(header);
        modal.appendChild(controls);
        modal.appendChild(list);
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
        status.textContent = translate("Loading...");

        editorFetch(textarea.dataset.blogCategoryTreeUrl, {
            headers: {"X-Requested-With": "XMLHttpRequest"},
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return {response: response, data: data};
                });
            })
            .then(function (result) {
                if (!result.response.ok) {
                    throw new Error(result.data.error || "Could not load blog categories.");
                }
                categories = result.data.items || [];
                if (!categories.length) {
                    status.textContent = translate("No categories found");
                    return;
                }
                renderCategories();
                searchInput.focus();
            })
            .catch(function (error) {
                console.error(error);
                status.textContent = translate(error.message || "Could not load blog categories.");
            });
    }

    function loadTemplateComponents() {
        if (templateComponents) {
            return Promise.resolve(templateComponents);
        }
        if (templateComponentsRequest) {
            return templateComponentsRequest;
        }
        if (!textarea.dataset.templateComponentsUrl) {
            templateComponents = [];
            return Promise.resolve(templateComponents);
        }

        templateComponentsRequest = editorFetch(textarea.dataset.templateComponentsUrl, {
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Components request failed.");
                }
                return response.json();
            })
            .then(function (data) {
                templateComponents = data.components || [];
                return templateComponents;
            })
            .catch(function (error) {
                templateComponentsRequest = null;
                throw error;
            });

        return templateComponentsRequest;
    }

    function openTemplateComponents() {
        const selection = {
            from: editor.getCursor("from"),
            to: editor.getCursor("to"),
        };
        const backdrop = document.createElement("div");
        const modal = document.createElement("div");
        const header = document.createElement("div");
        const heading = document.createElement("div");
        const closeButton = document.createElement("button");
        const controls = document.createElement("div");
        const searchInput = document.createElement("input");
        const filters = document.createElement("div");
        const grid = document.createElement("div");
        let activeCategory = "All";
        let components = [];

        backdrop.className = "template-code-modal-backdrop";
        modal.className = "template-code-modal template-code-component-modal";
        header.className = "template-code-modal-header";
        heading.className = "template-code-modal-title";
        heading.textContent = translate("Template components");
        closeButton.type = "button";
        closeButton.className = "template-code-modal-close";
        closeButton.setAttribute("aria-label", "Close template components");
        closeButton.innerHTML = (
            '<span class="material-symbols-outlined" aria-hidden="true">close</span>'
        );
        controls.className = "template-code-component-controls";
        searchInput.type = "search";
        searchInput.className = "template-code-component-search";
        searchInput.placeholder = "Search components";
        searchInput.setAttribute("aria-label", "Search template components");
        filters.className = "template-code-component-filters";
        grid.className = "template-code-component-grid";

        function closeModal() {
            backdrop.remove();
            editor.focus();
        }

        function insertCode(code) {
            editor.replaceRange(code, selection.from, selection.to);
            const fromIndex = editor.indexFromPos(selection.from);
            editor.setSelection(
                selection.from,
                editor.posFromIndex(fromIndex + code.length)
            );
            editor.focus();
            editor.refresh();
            closeModal();
        }

        function insertComponent(component) {
            if (
                component.slug === "latest-blog-articles" ||
                component.slug === "tags-cloud" ||
                component.slug === "images"
            ) {
                const modules = component.modules || [];
                if (!modules.length) {
                    if (component.slug === "tags-cloud") {
                        alert(
                            "No tags module has been created yet. " +
                            "Create one in Blog manager → Modules — Tags."
                        );
                    } else if (component.slug === "images") {
                        alert(
                            "No images module has been created yet. " +
                            "Create one in Images manager → Modules — Images."
                        );
                    } else {
                        alert(
                            "No latest articles module has been created yet. " +
                            "Create one in Blog manager → Modules — Latest articles."
                        );
                    }
                    return;
                }
                openChoiceModal(
                    component.slug === "tags-cloud"
                        ? "Choose tags module"
                        : component.slug === "images"
                            ? "Choose images module"
                            : "Choose latest articles module",
                    modules,
                    function (module) {
                        return module.name;
                    },
                    function (module) {
                        insertCode(module.code);
                    }
                );
                return;
            }
            insertCode(component.code);
        }

        function createFilterButton(category) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "template-code-component-filter";
            button.textContent = translate(category);
            button.classList.toggle("is-active", category === activeCategory);
            button.addEventListener("click", function () {
                activeCategory = category;
                filters.querySelectorAll(".template-code-component-filter").forEach(
                    option => option.classList.toggle("is-active", option === button)
                );
                renderComponents();
            });
            return button;
        }

        function createComponentCard(component) {
            const card = document.createElement("button");
            const icon = document.createElement("span");
            const content = document.createElement("span");
            const title = document.createElement("strong");
            const meta = document.createElement("span");
            const description = document.createElement("span");

            card.type = "button";
            card.className = "template-code-component-card";
            icon.className = "material-symbols-outlined template-code-component-icon";
            icon.setAttribute("aria-hidden", "true");
            icon.textContent = component.icon || "view_cozy";
            content.className = "template-code-component-content";
            title.textContent = component.name;
            meta.className = "template-code-component-meta";
            meta.textContent = component.category;
            description.className = "template-code-component-description";
            description.textContent = component.description || "";

            content.appendChild(title);
            content.appendChild(meta);
            content.appendChild(description);
            card.appendChild(icon);
            card.appendChild(content);
            card.addEventListener("click", function () {
                insertComponent(component);
            });
            return card;
        }

        function renderComponents() {
            const query = searchInput.value.trim().toLowerCase();
            const filtered = components.filter(function (component) {
                const matchesCategory = (
                    activeCategory === "All" || component.category === activeCategory
                );
                const haystack = [
                    component.name,
                    component.slug,
                    component.category,
                    component.description,
                ].join(" ").toLowerCase();
                const matchesQuery = (
                    !query ||
                    haystack.includes(query)
                );
                return matchesCategory && matchesQuery;
            });

            grid.replaceChildren();
            if (!filtered.length) {
                const empty = document.createElement("div");
                empty.className = "template-code-component-empty";
                empty.innerHTML = (
                    '<span class="material-symbols-outlined" aria-hidden="true">search_off</span>' +
                    "<span>No components found.</span>"
                );
                grid.appendChild(empty);
                return;
            }

            filtered.forEach(function (component) {
                grid.appendChild(createComponentCard(component));
            });
        }

        function renderFilters() {
            const categories = ["All"].concat(
                Array.from(new Set(components.map(component => component.category)))
            );
            filters.replaceChildren();
            categories.forEach(function (category) {
                filters.appendChild(createFilterButton(category));
            });
        }

        searchInput.addEventListener("input", renderComponents);
        closeButton.addEventListener("click", closeModal);
        backdrop.addEventListener("click", function (event) {
            if (event.target === backdrop) {
                closeModal();
            }
        });

        controls.appendChild(searchInput);
        controls.appendChild(filters);
        header.appendChild(heading);
        header.appendChild(closeButton);
        modal.appendChild(header);
        modal.appendChild(controls);
        modal.appendChild(grid);
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
        searchInput.focus();

        grid.innerHTML = (
            '<div class="template-code-component-empty">' +
            '<span class="material-symbols-outlined" aria-hidden="true">hourglass_empty</span>' +
            "<span>Loading components...</span>" +
            "</div>"
        );
        loadTemplateComponents()
            .then(function (loadedComponents) {
                components = loadedComponents;
                renderFilters();
                renderComponents();
            })
            .catch(function (error) {
                grid.innerHTML = (
                    '<div class="template-code-component-empty">' +
                    '<span class="material-symbols-outlined" aria-hidden="true">error</span>' +
                    "<span>" + error.message + "</span>" +
                    "</div>"
                );
            });
    }

    function openVersionHistory() {
        if (!textarea.dataset.historyUrl) {
            alert("Save the template before opening version history.");
            return;
        }

        const backdrop = document.createElement("div");
        const modal = document.createElement("div");
        const header = document.createElement("div");
        const heading = document.createElement("div");
        const closeButton = document.createElement("button");
        const body = document.createElement("div");
        const versionList = document.createElement("div");
        const comparison = document.createElement("div");

        backdrop.className = "template-code-modal-backdrop";
        modal.className = "template-code-modal template-code-history-modal";
        header.className = "template-code-modal-header";
        heading.className = "template-code-modal-title";
        heading.textContent = translate("Template version history");
        closeButton.type = "button";
        closeButton.className = "template-code-modal-close";
        closeButton.setAttribute("aria-label", "Close version history");
        closeButton.innerHTML = (
            '<span class="material-symbols-outlined" aria-hidden="true">close</span>'
        );
        body.className = "template-code-history-body";
        versionList.className = "template-code-history-list";
        comparison.className = "template-code-history-comparison";
        comparison.innerHTML = (
            '<div class="template-code-history-empty">' +
            '<span class="material-symbols-outlined" aria-hidden="true">difference</span>' +
            '<span>Select a version to compare it with the current editor.</span>' +
            '</div>'
        );

        function closeModal() {
            backdrop.remove();
        }

        function renderDiff(data, version) {
            comparison.replaceChildren();

            const summary = document.createElement("div");
            const summaryText = document.createElement("div");
            const stats = document.createElement("div");
            const restoreButton = document.createElement("button");
            const diff = document.createElement("pre");

            summary.className = "template-code-history-summary";
            summaryText.className = "template-code-history-summary-text";
            const summaryTitle = document.createElement("strong");
            const summaryMeta = document.createElement("span");
            summaryTitle.textContent = version.created_at_display;
            summaryMeta.textContent = version.author + " · " + version.source_display;
            summaryText.appendChild(summaryTitle);
            summaryText.appendChild(summaryMeta);
            stats.className = "template-code-history-stats";
            stats.innerHTML = (
                '<span class="is-added">+' + data.added + "</span>" +
                '<span class="is-removed">-' + data.removed + "</span>"
            );
            restoreButton.type = "button";
            restoreButton.className = "template-code-history-restore";
            restoreButton.innerHTML = (
                '<span class="material-symbols-outlined" aria-hidden="true">restore</span>' +
                "<span>Restore this version</span>"
            );
            restoreButton.addEventListener("click", function () {
                if (!confirm(
                    "Restore this saved version now? The current saved code will be kept in history."
                )) {
                    return;
                }

                const formData = new FormData();
                formData.append("version_id", version.id);
                formData.append("current_code", editor.getValue());

                editorFetch(textarea.dataset.historyRestoreUrl, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                    body: formData,
                })
                    .then(response => response.json())
                    .then(result => {
                        if (!result.success) {
                            alert(result.error || "Version restore failed.");
                            return;
                        }

                        editor.setValue(result.code || "");
                        editor.focus();
                        editor.refresh();
                        closeModal();
                        console.info(result.message);
                    })
                    .catch(error => {
                        console.error(error);
                        alert("Version restore failed.");
                    });
            });

            summary.appendChild(summaryText);
            summary.appendChild(stats);
            summary.appendChild(restoreButton);
            comparison.appendChild(summary);

            if (data.is_identical) {
                const identical = document.createElement("div");
                identical.className = "template-code-history-identical";
                identical.textContent = translate("This version is identical to the current editor.");
                comparison.appendChild(identical);
                return;
            }

            diff.className = "template-code-history-diff";
            data.diff.forEach(function (line) {
                const lineElement = document.createElement("span");
                lineElement.className = "template-code-history-diff-line";
                if (line.startsWith("+") && !line.startsWith("+++")) {
                    lineElement.classList.add("is-added");
                } else if (line.startsWith("-") && !line.startsWith("---")) {
                    lineElement.classList.add("is-removed");
                } else if (line.startsWith("@@")) {
                    lineElement.classList.add("is-range");
                } else if (line.startsWith("---") || line.startsWith("+++")) {
                    lineElement.classList.add("is-header");
                }
                lineElement.textContent = line || " ";
                diff.appendChild(lineElement);
            });
            comparison.appendChild(diff);
        }

        function compareVersion(version, button) {
            versionList.querySelectorAll(".template-code-history-item").forEach(
                function (item) {
                    item.classList.toggle("is-active", item === button);
                }
            );
            comparison.innerHTML = (
                '<div class="template-code-history-empty">' +
                '<span class="template-code-ajax-loader-spinner" aria-hidden="true"></span>' +
                "<span>Comparing version...</span>" +
                "</div>"
            );

            const formData = new FormData();
            formData.append("version_id", version.id);
            formData.append("current_code", editor.getValue());

            editorFetch(textarea.dataset.historyCompareUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: formData,
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        comparison.textContent = data.error;
                        return;
                    }
                    renderDiff(data, version);
                })
                .catch(error => {
                    console.error(error);
                    comparison.textContent = "Version comparison failed.";
                });
        }

        closeButton.addEventListener("click", closeModal);
        backdrop.addEventListener("click", function (event) {
            if (event.target === backdrop) {
                closeModal();
            }
        });
        header.appendChild(heading);
        header.appendChild(closeButton);
        body.appendChild(versionList);
        body.appendChild(comparison);
        modal.appendChild(header);
        modal.appendChild(body);
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);

        editorFetch(textarea.dataset.historyUrl)
            .then(response => response.json())
            .then(data => {
                versionList.replaceChildren();
                if (!data.versions || !data.versions.length) {
                    versionList.innerHTML = (
                        '<div class="template-code-history-list-empty">' +
                        "No previous versions yet. Change and save the template to create one." +
                        "</div>"
                    );
                    return;
                }

                data.versions.forEach(function (version, index) {
                    const button = document.createElement("button");
                    const title = document.createElement("strong");
                    const meta = document.createElement("span");
                    const size = document.createElement("span");

                    button.type = "button";
                    button.className = "template-code-history-item";
                    title.textContent = version.created_at_display;
                    meta.textContent = version.author + " · " + version.source_display;
                    size.textContent = (
                        version.line_count + " lines · " +
                        version.character_count + " characters"
                    );
                    button.appendChild(title);
                    button.appendChild(meta);
                    button.appendChild(size);
                    button.addEventListener("click", function () {
                        compareVersion(version, button);
                    });
                    versionList.appendChild(button);

                    if (index === 0) {
                        compareVersion(version, button);
                    }
                });
            })
            .catch(error => {
                console.error(error);
                versionList.textContent = translate("Could not load version history.");
            });
    }

    function openAssetBrowser() {
        if (!textarea.dataset.assetBrowserUrl) {
            alert("Asset browser is not available.");
            return;
        }

        const selection = {
            from: editor.getCursor("from"),
            to: editor.getCursor("to"),
        };
        const backdrop = document.createElement("div");
        const modal = document.createElement("div");
        const header = document.createElement("div");
        const heading = document.createElement("div");
        const closeButton = document.createElement("button");
        const uploadPanel = document.createElement("div");
        const targetSelect = document.createElement("select");
        const typeSelect = document.createElement("select");
        const pathInput = document.createElement("input");
        const fileInput = document.createElement("input");
        const uploadButton = document.createElement("button");
        const uploadStatus = document.createElement("span");
        const controls = document.createElement("div");
        const searchInput = document.createElement("input");
        const filters = document.createElement("div");
        const bulkActions = document.createElement("div");
        const selectVisibleButton = document.createElement("button");
        const clearSelectionButton = document.createElement("button");
        const deleteSelectedButton = document.createElement("button");
        const count = document.createElement("span");
        const grid = document.createElement("div");
        const assetBatchSize = 36;
        let assets = [];
        let activeType = "all";
        let filteredAssets = [];
        let renderedAssetCount = 0;
        let loadMoreObserver = null;
        const selectedAssetKeys = new Set();

        backdrop.className = "template-code-modal-backdrop";
        modal.className = "template-code-modal template-code-asset-modal";
        header.className = "template-code-modal-header";
        heading.className = "template-code-modal-title";
        heading.textContent = translate("Asset browser");
        closeButton.type = "button";
        closeButton.className = "template-code-modal-close";
        closeButton.setAttribute("aria-label", "Close asset browser");
        closeButton.innerHTML = (
            '<span class="material-symbols-outlined" aria-hidden="true">close</span>'
        );
        controls.className = "template-code-asset-controls";
        searchInput.type = "search";
        searchInput.className = "template-code-asset-search";
        searchInput.placeholder = "Search images by name or path";
        searchInput.setAttribute("aria-label", "Search image assets");
        filters.className = "template-code-asset-filters";
        bulkActions.className = "template-code-asset-bulk-actions";
        selectVisibleButton.type = "button";
        selectVisibleButton.className = "template-code-asset-bulk-button";
        selectVisibleButton.textContent = translate("Select visible");
        clearSelectionButton.type = "button";
        clearSelectionButton.className = "template-code-asset-bulk-button";
        clearSelectionButton.textContent = translate("Clear");
        deleteSelectedButton.type = "button";
        deleteSelectedButton.className = "template-code-asset-bulk-button is-danger";
        deleteSelectedButton.textContent = translate("Delete selected");
        deleteSelectedButton.disabled = true;
        count.className = "template-code-asset-count";
        count.setAttribute("aria-live", "polite");
        grid.className = "template-code-asset-grid";
        grid.innerHTML = (
            '<div class="template-code-asset-empty">' +
            '<span class="template-code-ajax-loader-spinner" aria-hidden="true"></span>' +
            "<span>Loading images...</span>" +
            "</div>"
        );
        uploadPanel.className = "template-code-asset-upload";
        targetSelect.className = "template-code-asset-upload-target";
        targetSelect.setAttribute("aria-label", "Choose an existing image to replace");
        typeSelect.className = "template-code-asset-upload-type";
        typeSelect.setAttribute("aria-label", "Upload storage");
        [
            ["static", "Static"],
            ["media", "Media"],
        ].forEach(function (choice) {
            const option = document.createElement("option");
            option.value = choice[0];
            option.textContent = choice[1];
            typeSelect.appendChild(option);
        });
        pathInput.type = "text";
        pathInput.className = "template-code-asset-upload-path";
        pathInput.placeholder = "themes/theme/assets/img/image.jpg";
        pathInput.setAttribute("aria-label", "Target image path and name");
        fileInput.type = "file";
        fileInput.className = "template-code-asset-upload-file";
        fileInput.accept = ".avif,.gif,.jpeg,.jpg,.png,.webp,image/avif,image/gif,image/jpeg,image/png,image/webp";
        uploadButton.type = "button";
        uploadButton.className = "template-code-asset-upload-button";
        uploadButton.textContent = translate("Upload image");
        uploadStatus.className = "template-code-asset-upload-status";
        uploadStatus.setAttribute("aria-live", "polite");

        function closeModal() {
            if (loadMoreObserver) {
                loadMoreObserver.disconnect();
            }
            backdrop.remove();
            editor.focus();
        }

        function insertAsset(asset) {
            editor.replaceRange(asset.insert_value, selection.from, selection.to);
            const insertedFromIndex = editor.indexFromPos(selection.from);
            const insertedTo = editor.posFromIndex(
                insertedFromIndex + asset.insert_value.length
            );
            editor.setSelection(selection.from, insertedTo);
            editor.scrollIntoView(
                {from: selection.from, to: insertedTo},
                80
            );
            editor.focus();
            editor.refresh();
            closeModal();
        }

        function assetKey(asset) {
            return asset.type + ":" + asset.path;
        }

        function getSelectedAssets() {
            return assets.filter(function (asset) {
                return selectedAssetKeys.has(assetKey(asset));
            });
        }

        function updateSelectionControls() {
            const selectedCount = selectedAssetKeys.size;
            deleteSelectedButton.disabled = selectedCount === 0;
            clearSelectionButton.disabled = selectedCount === 0;
            deleteSelectedButton.textContent = translate((
                selectedCount
                    ? "Delete selected (" + selectedCount + ")"
                    : "Delete selected"
            ));
        }

        function setAssetSelected(asset, isSelected) {
            const key = assetKey(asset);
            if (isSelected) {
                selectedAssetKeys.add(key);
            } else {
                selectedAssetKeys.delete(key);
            }
            updateSelectionControls();
        }

        function getTargetAsset() {
            return assets.find(function (asset) {
                return asset.type === typeSelect.value && asset.path === pathInput.value.trim();
            }) || null;
        }

        function updateUploadAction() {
            const targetAsset = getTargetAsset();
            uploadButton.textContent = translate(targetAsset ? "Replace image" : "Upload image");
            uploadButton.classList.toggle("is-replace", Boolean(targetAsset));
            targetSelect.value = targetAsset ? assetKey(targetAsset) : "";
        }

        function refreshTargetOptions(preferredKey) {
            const selectedKey = preferredKey || targetSelect.value;
            targetSelect.replaceChildren();
            const newOption = document.createElement("option");
            newOption.value = "";
            newOption.textContent = translate("New image (enter path and name)");
            targetSelect.appendChild(newOption);

            assets.forEach(function (asset) {
                const option = document.createElement("option");
                option.value = assetKey(asset);
                option.textContent = "[" + asset.type + "] " + asset.path;
                targetSelect.appendChild(option);
            });
            targetSelect.value = selectedKey;
        }

        function updateFilterCounts() {
            const staticCount = assets.filter(asset => asset.type === "static").length;
            const mediaCount = assets.filter(asset => asset.type === "media").length;
            filters.querySelector('[data-type="all"]').textContent = "All " + assets.length;
            filters.querySelector('[data-type="static"]').textContent = "Static " + staticCount;
            filters.querySelector('[data-type="media"]').textContent = "Media " + mediaCount;
        }

        function saveUploadedAsset() {
            const file = fileInput.files[0];
            const targetPath = pathInput.value.trim();
            const existingAsset = getTargetAsset();

            uploadStatus.className = "template-code-asset-upload-status";
            if (!file) {
                uploadStatus.textContent = translate("Choose an image from your computer.");
                uploadStatus.classList.add("is-error");
                return;
            }
            if (!targetPath) {
                uploadStatus.textContent = translate("Enter the target path and image name.");
                uploadStatus.classList.add("is-error");
                return;
            }
            if (existingAsset && !confirm("Replace " + existingAsset.path + "?")) {
                return;
            }

            const formData = new FormData();
            formData.append("image", file);
            formData.append("asset_type", typeSelect.value);
            formData.append("path", targetPath);
            formData.append("theme_id", getSelectedThemeId());
            formData.append("overwrite", existingAsset ? "true" : "false");
            uploadButton.disabled = true;
            uploadStatus.textContent = translate(existingAsset ? "Replacing image..." : "Uploading image...");

            editorFetch(textarea.dataset.assetBrowserUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: formData,
            })
                .then(response => response.json().then(data => ({response, data})))
                .then(function (result) {
                    if (!result.response.ok) {
                        throw new Error(result.data.error || "Could not upload image.");
                    }

                    const uploadedAsset = result.data.asset;
                    const existingIndex = assets.findIndex(function (asset) {
                        return assetKey(asset) === assetKey(uploadedAsset);
                    });
                    if (existingIndex === -1) {
                        assets.push(uploadedAsset);
                        assets.sort(function (left, right) {
                            return assetKey(left).localeCompare(assetKey(right));
                        });
                    } else {
                        assets[existingIndex] = uploadedAsset;
                    }

                    refreshTargetOptions(assetKey(uploadedAsset));
                    typeSelect.value = uploadedAsset.type;
                    pathInput.value = uploadedAsset.path;
                    fileInput.value = "";
                    updateUploadAction();
                    updateFilterCounts();
                    renderAssets();
                    uploadStatus.textContent = translate(result.data.message);
                    uploadStatus.classList.add("is-success");
                    updateSelectionControls();
                })
                .catch(function (error) {
                    console.error(error);
                    uploadStatus.textContent = translate(error.message || "Could not upload image.");
                    uploadStatus.classList.add("is-error");
                })
                .finally(function () {
                    uploadButton.disabled = false;
                });
        }

        function deleteSelectedAssets() {
            const selectedAssets = getSelectedAssets();
            if (!selectedAssets.length) {
                return;
            }
            if (!confirm("Delete " + selectedAssets.length + " selected image(s) permanently?")) {
                return;
            }

            const formData = new FormData();
            formData.append("action", "delete_many");
            formData.append("assets", JSON.stringify(selectedAssets.map(function (asset) {
                return {
                    type: asset.type,
                    path: asset.path,
                };
            })));

            deleteSelectedButton.disabled = true;
            uploadStatus.className = "template-code-asset-upload-status";
            uploadStatus.textContent = translate("Deleting selected images...");

            editorFetch(textarea.dataset.assetBrowserUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: formData,
            })
                .then(response => response.json().then(data => ({response, data})))
                .then(function (result) {
                    if (!result.response.ok) {
                        throw new Error(result.data.error || "Could not delete images.");
                    }

                    const deletedKeys = new Set((result.data.deleted || []).map(function (asset) {
                        return assetKey(asset);
                    }));
                    const failedItems = result.data.failed || [];
                    assets = assets.filter(function (asset) {
                        return !deletedKeys.has(assetKey(asset));
                    });
                    deletedKeys.forEach(function (key) {
                        selectedAssetKeys.delete(key);
                    });

                    refreshTargetOptions();
                    updateFilterCounts();
                    renderAssets();
                    uploadStatus.textContent = translate((
                        (result.data.message || "Images deleted.") +
                        (
                            failedItems.length
                                ? " Failed: " + failedItems.length + "."
                                : ""
                        )
                    ));
                    uploadStatus.classList.toggle("is-error", Boolean(failedItems.length));
                    uploadStatus.classList.toggle(
                        "is-success",
                        !failedItems.length
                    );
                    if (!deletedKeys.size || failedItems.length) {
                        alert(
                            "Deleted: " + deletedKeys.size + "\n" +
                            "Failed: " + failedItems.length +
                            (
                                failedItems.length
                                    ? "\n\n" + failedItems.slice(0, 8).map(function (item) {
                                        return item.path + ": " + item.error;
                                    }).join("\n")
                                    : ""
                            )
                        );
                    }
                })
                .catch(function (error) {
                    console.error(error);
                    uploadStatus.textContent = translate(error.message || "Could not delete images.");
                    uploadStatus.classList.add("is-error");
                    alert(uploadStatus.textContent);
                })
                .finally(updateSelectionControls);
        }

        function createFilter(type, label) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "template-code-asset-filter";
            button.dataset.type = type;
            button.textContent = translate(label);
            button.addEventListener("click", function () {
                activeType = type;
                filters.querySelectorAll(".template-code-asset-filter").forEach(
                    function (item) {
                        item.classList.toggle("is-active", item === button);
                    }
                );
                renderAssets();
            });
            filters.appendChild(button);
            return button;
        }

        function createAssetCard(asset) {
            const card = document.createElement("div");
            const selection = document.createElement("label");
            const checkbox = document.createElement("input");
            const checkIcon = document.createElement("span");
            const preview = document.createElement("span");
            const image = document.createElement("img");
            const fallback = document.createElement("span");
            const details = document.createElement("span");
            const name = document.createElement("strong");
            const path = document.createElement("span");
            const meta = document.createElement("span");
            const badge = document.createElement("span");

            card.className = "template-code-asset-card";
            card.tabIndex = 0;
            card.setAttribute("role", "button");
            card.title = "Insert " + asset.insert_value;
            selection.className = "template-code-asset-select";
            selection.title = "Select " + asset.path;
            checkbox.type = "checkbox";
            checkbox.checked = selectedAssetKeys.has(assetKey(asset));
            checkbox.setAttribute("aria-label", "Select " + asset.path);
            checkIcon.className = "material-symbols-outlined";
            checkIcon.setAttribute("aria-hidden", "true");
            checkIcon.textContent = "check";
            preview.className = "template-code-asset-preview";
            image.loading = "lazy";
            image.src = asset.preview_url + (
                asset.version
                    ? (asset.preview_url.includes("?") ? "&" : "?") + "v=" + asset.version
                    : ""
            );
            image.alt = asset.name;
            fallback.className = "material-symbols-outlined template-code-asset-fallback";
            fallback.textContent = "broken_image";
            image.addEventListener("error", function () {
                image.hidden = true;
                fallback.hidden = false;
            });
            fallback.hidden = true;
            details.className = "template-code-asset-details";
            name.textContent = asset.name;
            path.className = "template-code-asset-path";
            path.textContent = asset.path;
            meta.className = "template-code-asset-meta";
            meta.textContent = (
                asset.extension.toUpperCase() + " · " + asset.size_display
            );
            badge.className = (
                "template-code-asset-badge is-" + asset.type
            );
            badge.textContent = asset.type;

            selection.appendChild(checkbox);
            selection.appendChild(checkIcon);
            preview.appendChild(image);
            preview.appendChild(fallback);
            preview.appendChild(badge);
            details.appendChild(name);
            details.appendChild(path);
            details.appendChild(meta);
            card.appendChild(selection);
            card.appendChild(preview);
            card.appendChild(details);
            card.classList.toggle("is-selected", checkbox.checked);
            selection.classList.toggle("is-selected", checkbox.checked);
            checkbox.addEventListener("change", function () {
                setAssetSelected(asset, checkbox.checked);
                card.classList.toggle("is-selected", checkbox.checked);
                selection.classList.toggle("is-selected", checkbox.checked);
            });
            selection.addEventListener("click", function (event) {
                event.stopPropagation();
            });
            card.addEventListener("click", function (event) {
                if (event.target.closest(".template-code-asset-select")) {
                    return;
                }
                insertAsset(asset);
            });
            card.addEventListener("keydown", function (event) {
                if (event.key === "Enter") {
                    insertAsset(asset);
                }
                if (event.key === " ") {
                    event.preventDefault();
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event("change", {bubbles: true}));
                }
            });
            return card;
        }

        function stopObservingMoreAssets() {
            if (loadMoreObserver) {
                loadMoreObserver.disconnect();
                loadMoreObserver = null;
            }
        }

        function updateRenderedCount() {
            if (renderedAssetCount < filteredAssets.length) {
                count.textContent = translate((
                    renderedAssetCount + " of " + filteredAssets.length + " images"
                ));
                return;
            }
            count.textContent = translate(filteredAssets.length + " images");
        }

        function appendNextAssetBatch() {
            stopObservingMoreAssets();
            const nextCount = Math.min(
                renderedAssetCount + assetBatchSize,
                filteredAssets.length
            );
            const fragment = document.createDocumentFragment();

            filteredAssets.slice(renderedAssetCount, nextCount).forEach(function (asset) {
                fragment.appendChild(createAssetCard(asset));
            });
            grid.appendChild(fragment);
            renderedAssetCount = nextCount;
            updateRenderedCount();

            if (renderedAssetCount >= filteredAssets.length) {
                return;
            }

            const sentinel = document.createElement("button");
            sentinel.type = "button";
            sentinel.className = "template-code-asset-load-more";
            sentinel.innerHTML = (
                '<span class="template-code-ajax-loader-spinner" aria-hidden="true"></span>' +
                "<span>Scroll to load more images</span>"
            );
            sentinel.addEventListener("click", function () {
                sentinel.remove();
                appendNextAssetBatch();
            });
            grid.appendChild(sentinel);

            if ("IntersectionObserver" in window) {
                loadMoreObserver = new IntersectionObserver(function (entries) {
                    if (!entries.some(entry => entry.isIntersecting)) {
                        return;
                    }
                    stopObservingMoreAssets();
                    sentinel.remove();
                    appendNextAssetBatch();
                }, {
                    root: grid,
                    rootMargin: "320px 0px",
                    threshold: 0.01,
                });
                loadMoreObserver.observe(sentinel);
            }
        }

        function renderAssets() {
            const query = searchInput.value.trim().toLowerCase();
            filteredAssets = assets.filter(function (asset) {
                const typeMatches = (
                    activeType === "all" || asset.type === activeType
                );
                const queryMatches = (
                    !query ||
                    asset.name.toLowerCase().includes(query) ||
                    asset.path.toLowerCase().includes(query)
                );
                return typeMatches && queryMatches;
            });

            stopObservingMoreAssets();
            grid.replaceChildren();
            grid.scrollTop = 0;
            renderedAssetCount = 0;
            updateRenderedCount();
            if (!filteredAssets.length) {
                const empty = document.createElement("div");
                empty.className = "template-code-asset-empty";
                empty.innerHTML = (
                    '<span class="material-symbols-outlined" aria-hidden="true">image_search</span>' +
                    "<span>No images match this search.</span>"
                );
                grid.appendChild(empty);
                return;
            }
            appendNextAssetBatch();
        }

        const allFilter = createFilter("all", "All");
        createFilter("static", "Static");
        createFilter("media", "Media");
        allFilter.classList.add("is-active");
        searchInput.addEventListener("input", renderAssets);
        selectVisibleButton.addEventListener("click", function () {
            filteredAssets.forEach(function (asset) {
                selectedAssetKeys.add(assetKey(asset));
            });
            updateSelectionControls();
            renderAssets();
        });
        clearSelectionButton.addEventListener("click", function () {
            selectedAssetKeys.clear();
            updateSelectionControls();
            renderAssets();
        });
        deleteSelectedButton.addEventListener("click", deleteSelectedAssets);
        fileInput.addEventListener("change", function () {
            const file = fileInput.files[0];

            if (!file || pathInput.value.trim()) {
                return;
            }

            if (typeSelect.value === "static") {
                const themeSlug = getSelectedThemeSlug();

                if (themeSlug) {
                    pathInput.value = "themes/" + themeSlug + "/assets/img/" + file.name;
                } else {
                    pathInput.value = "assets/img/" + file.name;
                }
            } else {
                pathInput.value = file.name;
            }

            updateUploadAction();
        });
        targetSelect.addEventListener("change", function () {
            const selectedAsset = assets.find(function (asset) {
                return assetKey(asset) === targetSelect.value;
            });
            if (selectedAsset) {
                typeSelect.value = selectedAsset.type;
                pathInput.value = selectedAsset.path;
            }
            updateUploadAction();
        });
        typeSelect.addEventListener("change", updateUploadAction);
        pathInput.addEventListener("input", updateUploadAction);
        fileInput.addEventListener("change", function () {
            if (fileInput.files[0] && !pathInput.value.trim()) {
                pathInput.value = fileInput.files[0].name;
                updateUploadAction();
            }
        });
        uploadButton.addEventListener("click", saveUploadedAsset);
        searchInput.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeModal();
            }
        });
        closeButton.addEventListener("click", closeModal);
        backdrop.addEventListener("click", function (event) {
            if (event.target === backdrop) {
                closeModal();
            }
        });

        header.appendChild(heading);
        header.appendChild(closeButton);
        uploadPanel.appendChild(targetSelect);
        uploadPanel.appendChild(typeSelect);
        uploadPanel.appendChild(pathInput);
        uploadPanel.appendChild(fileInput);
        uploadPanel.appendChild(uploadButton);
        uploadPanel.appendChild(uploadStatus);
        controls.appendChild(searchInput);
        controls.appendChild(filters);
        bulkActions.appendChild(selectVisibleButton);
        bulkActions.appendChild(clearSelectionButton);
        bulkActions.appendChild(deleteSelectedButton);
        controls.appendChild(bulkActions);
        controls.appendChild(count);
        modal.appendChild(header);
        modal.appendChild(uploadPanel);
        modal.appendChild(controls);
        modal.appendChild(grid);
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);

        editorFetch(textarea.dataset.assetBrowserUrl)
            .then(response => response.json().then(data => ({
                response: response,
                data: data,
            })))
            .then(result => {
                if (!result.response.ok) {
                    throw new Error(
                        result.data.error || "Could not load image assets."
                    );
                }
                assets = result.data.assets || [];
                refreshTargetOptions();
                updateFilterCounts();
                renderAssets();
                searchInput.focus();
            })
            .catch(error => {
                console.error(error);
                grid.innerHTML = "";
                const empty = document.createElement("div");
                empty.className = "template-code-asset-empty is-error";
                empty.textContent = translate(error.message || "Could not load image assets.");
                grid.appendChild(empty);
            });
    }

    function parseJson(value, fallback) {
        try {
            return JSON.parse(value || "");
        } catch (error) {
            return fallback;
        }
    }

    let pendingAjaxRequests = 0;
    const ajaxLoader = document.createElement("div");
    ajaxLoader.className = "template-code-ajax-loader";
    ajaxLoader.setAttribute("role", "status");
    ajaxLoader.setAttribute("aria-live", "polite");
    ajaxLoader.setAttribute("aria-hidden", "true");
    ajaxLoader.innerHTML = [
        '<div class="template-code-ajax-loader-panel">',
        '<span class="template-code-ajax-loader-spinner" aria-hidden="true"></span>',
        '<span class="template-code-ajax-loader-text">Processing...</span>',
        '</div>',
    ].join("");
    document.body.appendChild(ajaxLoader);

    function setAjaxLoaderVisible(isVisible) {
        ajaxLoader.classList.toggle("is-visible", isVisible);
        ajaxLoader.setAttribute("aria-hidden", isVisible ? "false" : "true");
        document.body.classList.toggle("template-code-ajax-busy", isVisible);
    }

    function startAjaxLoader() {
        pendingAjaxRequests += 1;
        setAjaxLoaderVisible(true);
    }

    function stopAjaxLoader() {
        pendingAjaxRequests = Math.max(0, pendingAjaxRequests - 1);
        if (pendingAjaxRequests === 0) {
            setAjaxLoaderVisible(false);
        }
    }

    function runEditorAction(action, event) {
        startAjaxLoader();

        window.requestAnimationFrame(function () {
            try {
                Promise.resolve(action(event)).finally(stopAjaxLoader);
            } catch (error) {
                stopAjaxLoader();
                throw error;
            }
        });
    }

    function editorFetch(url, options) {
        startAjaxLoader();

        return window.fetch(url, options).finally(function () {
            stopAjaxLoader();
        });
    }
    function runAiAction(action, extraData, selectionData) {
        if (!textarea.dataset.aiTransformUrl) {
            alert("Please save the template before using this action.");
            return;
        }

        const selection = selectionData || {
            code: editor.getSelection(),
            from: editor.getCursor("from"),
            to: editor.getCursor("to"),
        };
        const formData = new FormData();
        formData.append("selected_code", selection.code);
        formData.append("action", action);

        if (extraData) {
            Object.keys(extraData).forEach(function (key) {
                formData.append(key, extraData[key]);
            });
        }

        editorFetch(textarea.dataset.aiTransformUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: formData,
        })
            .then(response => response.json())
            .then(data => {
                if (data.code) {
                    editor.replaceRange(data.code, selection.from, selection.to);
                    editor.focus();
                    editor.refresh();
                    if (data.include_name) {
                        console.info("Include block created: " + data.include_name);
                    }
                } else {
                    alert(data.error || "AI transform failed.");
                }
            })
            .catch(error => {
                console.error(error);
                alert("AI transform failed.");
            });
    }

    function getExpandedImageSelection() {
        const selectedCode = editor.getSelection();
        const from = editor.getCursor("from");
        const to = editor.getCursor("to");
        const fullCode = editor.getValue();
        const fromIndex = editor.indexFromPos(from);
        const toIndex = editor.indexFromPos(to);
        const patterns = [
            /{%\s*static\s+(['"]).*?\1\s*%}/gi,
            /<img\b[^>]*>/gi,
        ];

        for (let patternIndex = 0; patternIndex < patterns.length; patternIndex += 1) {
            const pattern = patterns[patternIndex];
            let match = pattern.exec(fullCode);

            while (match) {
                const matchStart = match.index;
                const matchEnd = matchStart + match[0].length;

                if (matchStart <= fromIndex && matchEnd >= toIndex) {
                    return {
                        code: match[0],
                        from: editor.posFromIndex(matchStart),
                        to: editor.posFromIndex(matchEnd),
                    };
                }

                match = pattern.exec(fullCode);
            }
        }

        return {
            code: selectedCode,
            from: from,
            to: to,
        };
    }

    function formatLoadAnalysis(data) {
        const lines = [];

        if (data.missing && data.missing.length) {
            lines.push("ADD:");
            data.missing.forEach(function (item) {
                lines.push(item.statement + " for: " + item.symbols.join(", "));
            });
        }

        if (data.unused && data.unused.length) {
            lines.push("", "REMOVE AS UNUSED:");
            data.unused.forEach(function (libraryName) {
                lines.push("{% load " + libraryName + " %}");
            });
        }

        if (data.unknown && data.unknown.length) {
            lines.push("", "UNKNOWN LIBRARIES:");
            data.unknown.forEach(function (libraryName) {
                lines.push(libraryName);
            });
        }

        if (data.ambiguous && data.ambiguous.length) {
            lines.push("", "CHECK MANUALLY:");
            data.ambiguous.forEach(function (item) {
                lines.push(item.symbol + " may belong to: " + item.libraries.join(", "));
            });
        }

        if (data.syntax_errors && data.syntax_errors.length) {
            lines.push("", "DJANGO TEMPLATE ERRORS:");
            data.syntax_errors.forEach(function (message) {
                lines.push(message);
            });
        }

        if (data.django_block_errors && data.django_block_errors.length) {
            lines.push("", "DJANGO BLOCK ERRORS:");
            data.django_block_errors.forEach(function (item) {
                lines.push(
                    (item.line ? "Line " + item.line + ": " : "") + item.message
                );
            });
        }

        if (data.html_errors && data.html_errors.length) {
            lines.push("", "HTML TAG ERRORS:");
            data.html_errors.forEach(function (item) {
                lines.push(
                    (item.line ? "Line " + item.line + ": " : "") + item.message
                );
            });
        }

        if (data.url_issues && data.url_issues.length) {
            lines.push("", "STATIC / MEDIA URL ISSUES:");
            data.url_issues.forEach(function (item) {
                lines.push(
                    (item.line ? "Line " + item.line + ": " : "") + item.message
                );
            });
        }

        if (data.duplicate_ids && data.duplicate_ids.length) {
            lines.push("", "DUPLICATE HTML IDS:");
            data.duplicate_ids.forEach(function (item) {
                lines.push(item.message);
            });
        }

        if (!lines.length) {
            return (
                "Template check passed.\n" +
                "HTML, Django syntax, load libraries, URLs, and IDs look correct."
            );
        }

        return lines.join("\n").replace(/^\n+/, "");
    }

    function analyzeTemplateLoads() {
        if (!textarea.dataset.analyzeLoadsUrl) {
            alert("Please save the template before using this action.");
            return;
        }

        const formData = new FormData();
        formData.append("code", editor.getValue());

        editorFetch(textarea.dataset.analyzeLoadsUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: formData,
        })
            .then(response => response.json().then(data => ({response: response, data: data})))
            .then(result => {
                if (!result.response.ok) {
                    alert(result.data.error || "Template load check failed.");
                    return;
                }
                console.info(formatLoadAnalysis(result.data));
            })
            .catch(error => {
                console.error(error);
                alert("Template load check failed.");
            });
    }

    function formatTemplateCode() {
        const formatUrl = textarea.dataset.formatUrl || (
            textarea.dataset.analyzeLoadsUrl
                ? textarea.dataset.analyzeLoadsUrl.replace(
                    /analyze-loads\/?$/,
                    "format/"
                )
                : ""
        );

        if (!formatUrl) {
            alert("Please save the template before using this action.");
            return;
        }

        const cursor = editor.getCursor();
        const scrollInfo = editor.getScrollInfo();
        const currentCode = editor.getValue();
        const formData = new FormData();
        formData.append("code", currentCode);

        editorFetch(formatUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: formData,
        })
            .then(async function (response) {
                const contentType = response.headers.get("content-type") || "";
                if (!contentType.includes("application/json")) {
                    const responseText = await response.text();
                    throw new Error(
                        "Format endpoint returned HTML instead of JSON " +
                        "(HTTP " + response.status + "). " +
                        "Reload the admin page or restart the Django server. " +
                        responseText.slice(0, 80)
                    );
                }
                return {
                    response: response,
                    data: await response.json(),
                };
            })
            .then(result => {
                if (!result.response.ok) {
                    alert(result.data.error || "Template formatting failed.");
                    return;
                }

                const formattedCode = result.data.code || "";
                if (formattedCode === currentCode) {
                    return;
                }

                editor.operation(function () {
                    const lastLine = Math.max(0, editor.lineCount() - 1);
                    const lastCharacter = editor.getLine(lastLine).length;
                    editor.replaceRange(
                        formattedCode,
                        {line: 0, ch: 0},
                        {line: lastLine, ch: lastCharacter}
                    );
                    editor.setCursor(cursor);
                    editor.scrollTo(scrollInfo.left, scrollInfo.top);
                });
                editor.save();
                textarea.dispatchEvent(new Event("input", {bubbles: true}));
                textarea.dispatchEvent(new Event("change", {bubbles: true}));
                editor.focus();
                window.requestAnimationFrame(function () {
                    editor.refresh();
                });
            })
            .catch(error => {
                console.error(error);
                alert(error.message || "Template formatting failed.");
            });
    }

    function normalizeSeoHead() {
        let code = editor.getValue();
        const seoHeadBlock = [
            "<meta charset=\"utf-8\">",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            "",
            "<title>{{ title }}</title>",
            "<meta name=\"description\" content=\"{{ description }}\">",
            "<meta name=\"author\" content=\"{{ author }}\">",
            "<meta name=\"robots\" content=\"{{ robots }}\">",
            "",
            "<link rel=\"canonical\" href=\"{{ canonical_url }}\">",
            "",
            "{{ alternate_links|safe }}",
            "",
            "<link rel=\"preconnect\" href=\"{{ base_url }}\" crossorigin>",
            "",
            "<meta property=\"og:title\" content=\"{{ title }}\">",
            "<meta property=\"og:description\" content=\"{{ description }}\">",
            "<meta property=\"og:type\" content=\"{{ type_content }}\">",
            "<meta property=\"og:url\" content=\"{{ canonical_url }}\">",
            "<meta property=\"og:site_name\" content=\"{{ og_site_name }}\">",
            "<meta property=\"og:locale\" content=\"{{ og_locale }}\">",
            "",
            "<meta property=\"og:image\" content=\"{{ preview_url }}\">",
            "<meta property=\"og:image:secure_url\" content=\"{{ preview_url }}\">",
            "<meta property=\"og:image:type\" content=\"{{ preview_mime }}\">",
            "<meta property=\"og:image:width\" content=\"{{ preview_width }}\">",
            "<meta property=\"og:image:height\" content=\"{{ preview_height }}\">",
            "<meta property=\"og:image:alt\" content=\"{{ image_alt }}\">",
            "",
            "{{ article_meta|safe }}",
            "",
            "<meta name=\"twitter:card\" content=\"summary_large_image\">",
            "<meta name=\"twitter:title\" content=\"{{ title }}\">",
            "<meta name=\"twitter:description\" content=\"{{ description }}\">",
            "<meta name=\"twitter:image\" content=\"{{ preview_url }}\">",
            "<meta name=\"twitter:image:alt\" content=\"{{ image_alt }}\">",
            "<meta name=\"twitter:site\" content=\"{{ twitter }}\">",
            "<meta name=\"twitter:creator\" content=\"{{ twitter }}\">",
            "",
            "<meta name=\"theme-color\" content=\"{{ theme_color }}\">",
            "<meta name=\"msapplication-TileColor\" content=\"{{ theme_color }}\">",
            "",
            "<link rel=\"icon\" href=\"/favicon.ico\" sizes=\"any\">",
            "<link rel=\"icon\" type=\"image/png\" href=\"/favicon.png\">",
            "<link rel=\"apple-touch-icon\" href=\"/apple-touch-icon.png\">",
            "",
            "<script type=\"application/ld+json\">{{ schema_graph|safe }}</script>",
        ].join("\n");
        const preservedPatterns = [
            /<script\b[^>]*>[\s\S]*?<\/script>/gi,
            /<style\b[^>]*>[\s\S]*?<\/style>/gi,
            /<noscript\b[^>]*>[\s\S]*?<\/noscript>/gi,
            /<link\b(?=[^>]*\brel=["'][^"']*(?:stylesheet|preload|modulepreload)[^"']*["'])[^>]*>/gi,
        ];

        function indentHeadCode(value) {
            return value
                .split("\n")
                .map(function (line) {
                    if (!line.trim()) {
                        return "";
                    }

                    return "    " + line.trim();
                })
                .join("\n");
        }

        code = code.replace(/<html\b[^>]*>/i, "<html lang=\"{{ lang }}\">");

        const headMatch = code.match(/<head\b[^>]*>[\s\S]*?<\/head>/i);

        if (!headMatch) {
            alert("No <head> tag found.");
            return;
        }

        const normalizedHead = headMatch[0].replace(
            /(<head\b[^>]*>)([\s\S]*?)(<\/head>)/i,
            function (match, openTag, headContent, closeTag) {
                const preserved = [];

                preservedPatterns.forEach(function (pattern) {
                    const matches = headContent.match(pattern) || [];
                    matches.forEach(function (item) {
                        if (/^<script\b/i.test(item) && /type=["']application\/ld\+json["']/i.test(item)) {
                            return;
                        }
                        if (!preserved.includes(item)) {
                            preserved.push(item.trim());
                        }
                    });
                });

                const body = [
                    seoHeadBlock,
                    preserved.join("\n\n"),
                ].filter(Boolean).join("\n\n");

                return openTag + "\n" + indentHeadCode(body) + "\n" + closeTag;
            }
        );

        editor.setValue(code.replace(headMatch[0], normalizedHead));
        editor.refresh();
    }

    const djangoTemplateTags = [
        "block", "endblock", "extends", "include", "load", "static", "url",
        "if", "elif", "else", "endif", "for", "empty", "endfor", "with",
        "endwith", "trans", "blocktrans", "endblocktrans", "csrf_token",
        "comment", "endcomment", "autoescape", "endautoescape", "now",
    ];
    const djangoTemplateVariables = [
        "request", "request.path", "request.user", "user", "user.is_authenticated",
        "LANGUAGE_CODE", "LANGUAGE_BIDI", "site_settings", "page_obj", "object",
        "messages", "perms",
    ];

    function djangoTemplateHint(codeEditor) {
        const cursor = codeEditor.getCursor();
        const lineBeforeCursor = codeEditor.getLine(cursor.line).slice(0, cursor.ch);
        const tagMatch = lineBeforeCursor.match(/\{%\s*([\w]*)$/);
        const variableMatch = lineBeforeCursor.match(/\{\{\s*([\w.]*)$/);
        const match = tagMatch || variableMatch;

        if (!match) {
            return null;
        }

        const typedText = match[1];
        const candidates = tagMatch ? djangoTemplateTags : djangoTemplateVariables;
        const list = candidates.filter(function (candidate) {
            return candidate.toLowerCase().startsWith(typedText.toLowerCase());
        });

        return {
            list: list,
            from: CodeMirror.Pos(cursor.line, cursor.ch - typedText.length),
            to: cursor,
        };
    }

    function templateCodeHint(codeEditor, options) {
        return djangoTemplateHint(codeEditor)
            || CodeMirror.hint.html(codeEditor, options);
    }

    function openTemplateCodeHints(codeEditor) {
        codeEditor.showHint({
            completeSingle: false,
            hint: templateCodeHint,
        });
    }

    function openDjangoHintsWhileTyping(codeEditor) {
        if (codeEditor.state.completionActive) {
            return;
        }

        const cursor = codeEditor.getCursor();
        const lineBeforeCursor = codeEditor.getLine(cursor.line).slice(0, cursor.ch);

        if (!/\{(?:%|\{)\s*[\w.]*$/.test(lineBeforeCursor)) {
            return;
        }

        window.setTimeout(function () {
            if (!codeEditor.state.completionActive) {
                openTemplateCodeHints(codeEditor);
            }
        }, 0);
    }

    const editor = CodeMirror.fromTextArea(textarea, {
        mode: "htmlmixed",
        theme: "material-darker",
        indentUnit: 4,
        tabSize: 4,
        lineNumbers: true,
        lineWrapping: false,
        autoCloseBrackets: true,
        autoCloseTags: true,
        matchTags: { bothTags: true },
        styleActiveLine: true,
        styleSelectedText: true,
        foldGutter: true,
        gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
        extraKeys: {
            "Ctrl-Q": function (codeEditor) {
                codeEditor.foldCode(codeEditor.getCursor());
            },
            "Ctrl-Space": openTemplateCodeHints,
        },
        viewportMargin: Infinity
    });

    function renderIndentGuides(codeEditor, line, element) {
        const leadingWhitespace = (line.text.match(/^[\t ]+/) || [""])[0];

        if (!leadingWhitespace) {
            return;
        }

        let columns = 0;

        for (const character of leadingWhitespace) {
            columns += character === "\t"
                ? codeEditor.getOption("tabSize") - (columns % codeEditor.getOption("tabSize"))
                : 1;
        }

        if (columns < codeEditor.getOption("indentUnit")) {
            return;
        }

        const characterWidth = codeEditor.defaultCharWidth();
        element.classList.add("template-code-line-with-indent");
        element.style.setProperty(
            "--template-code-indent-width",
            (columns * characterWidth + 1) + "px"
        );
        element.style.setProperty(
            "--template-code-indent-step",
            (codeEditor.getOption("indentUnit") * characterWidth) + "px"
        );
    }

    let pendingTagRename = null;
    let isSyncingTagRename = false;

    function tagNameRange(tag, isClosing) {
        const start = CodeMirror.Pos(
            tag.from.line,
            tag.from.ch + (isClosing ? 2 : 1)
        );

        return {
            from: start,
            to: CodeMirror.Pos(start.line, start.ch + tag.tag.length),
        };
    }

    function positionIsInsideRange(position, range, allowEnd) {
        if (position.line !== range.from.line || position.line !== range.to.line) {
            return false;
        }

        return position.ch >= range.from.ch
            && position.ch <= range.to.ch
            && (allowEnd || position.ch < range.to.ch);
    }

    function rememberMatchingTagBeforeChange(codeEditor, change) {
        pendingTagRename = null;

        if (
            isSyncingTagRename
            || change.origin === "setValue"
            || change.from.line !== change.to.line
            || change.text.length !== 1
            || typeof CodeMirror.findMatchingTag !== "function"
        ) {
            return;
        }

        const matching = CodeMirror.findMatchingTag(codeEditor, change.from);

        if (!matching || !matching.open || !matching.close) {
            return;
        }

        const editingClosingTag = matching.at === "close";
        const currentTag = editingClosingTag ? matching.close : matching.open;
        const partnerTag = editingClosingTag ? matching.open : matching.close;
        const currentRange = tagNameRange(currentTag, editingClosingTag);
        const partnerRange = tagNameRange(partnerTag, !editingClosingTag);

        if (
            !positionIsInsideRange(change.from, currentRange, true)
            || !positionIsInsideRange(change.to, currentRange, true)
        ) {
            return;
        }

        pendingTagRename = {
            changeFrom: change.from,
            changeTo: change.to,
            currentRange: currentRange,
            partnerRange: partnerRange,
            insertedText: change.text[0],
        };
    }

    function shiftRangeAfterSingleLineChange(range, rename) {
        const removedLength = rename.changeTo.ch - rename.changeFrom.ch;
        const difference = rename.insertedText.length - removedLength;

        if (
            range.from.line === rename.changeTo.line
            && range.from.ch >= rename.changeTo.ch
        ) {
            return {
                from: CodeMirror.Pos(range.from.line, range.from.ch + difference),
                to: CodeMirror.Pos(range.to.line, range.to.ch + difference),
            };
        }

        return range;
    }

    function syncMatchingTagAfterChange(codeEditor) {
        const rename = pendingTagRename;
        pendingTagRename = null;

        if (!rename || isSyncingTagRename) {
            return;
        }

        const currentRange = {
            from: rename.currentRange.from,
            to: CodeMirror.Pos(
                rename.currentRange.to.line,
                rename.currentRange.to.ch
                    + rename.insertedText.length
                    - (rename.changeTo.ch - rename.changeFrom.ch)
            ),
        };
        const newTagName = codeEditor.getRange(currentRange.from, currentRange.to);

        if (!/^[A-Za-z][\w:-]*$/.test(newTagName)) {
            return;
        }

        const partnerRange = shiftRangeAfterSingleLineChange(
            rename.partnerRange,
            rename
        );

        isSyncingTagRename = true;
        codeEditor.replaceRange(
            newTagName,
            partnerRange.from,
            partnerRange.to,
            "+sync-tag-name"
        );
        isSyncingTagRename = false;
    }

    editor.on("beforeChange", rememberMatchingTagBeforeChange);
    editor.on("change", syncMatchingTagAfterChange);
    editor.on("renderLine", renderIndentGuides);
    editor.on("inputRead", openDjangoHintsWhileTyping);
    editor.refresh();

    editor.setSize("100%", 720);
    textarea._wulverCodeMirror = editor;
    document.dispatchEvent(new CustomEvent("wulver:code-editor-ready", {
        detail: {
            textarea: textarea,
            editor: editor,
        },
    }));

    const toolbar = document.createElement("div");
    toolbar.className = "template-code-toolbar";
    const searchReplace = createSearchReplacePanel();
    editor.addKeyMap({
        "Ctrl-H": function () {
            searchReplace.open();
        },
        "Cmd-Alt-F": function () {
            searchReplace.open();
        },
    });

    const themeSelect = document.getElementById("id_theme");
    const themeHtmlFiles = parseJson(textarea.dataset.themeHtmlFiles, {});
    const themeIncludeBlocks = parseJson(textarea.dataset.themeIncludeBlocks, {});
    const themeBaseTemplates = parseJson(textarea.dataset.themeBaseTemplates, {});
    const themeSlugs = parseJson(textarea.dataset.themeSlugs, {});
    const htmlFiles = parseJson(textarea.dataset.htmlFiles, []);

    function getSelectedThemeId() {
        if (themeSelect) {
            return themeSelect.value;
        }

        return textarea.dataset.themeId || "";
    }

    function getFilesForSelectedTheme() {
        const themeId = getSelectedThemeId();

        if (themeId && themeHtmlFiles[themeId]) {
            return themeHtmlFiles[themeId];
        }

        return htmlFiles;
    }

    function getSelectedThemeSlug() {
        const themeId = getSelectedThemeId();

        return themeSlugs[themeId] || "";
    }

    function getIncludeBlocksForSelectedTheme() {
        const themeId = getSelectedThemeId();

        if (themeId && themeIncludeBlocks[themeId]) {
            return themeIncludeBlocks[themeId];
        }

        return [];
    }

    function getBaseTemplatesForSelectedTheme() {
        const themeId = getSelectedThemeId();

        if (themeId && themeBaseTemplates[themeId]) {
            return themeBaseTemplates[themeId];
        }

        return [];
    }

    function buildExtendsTemplate(code, extendsTag) {
        const normalizedCode = (code || "").trim();
        const withoutExistingExtends = normalizedCode.replace(
            /^\s*{% extends\s+["'][^"']+["'] %}\s*/i,
            ""
        ).trim();
        const loadTags = [];
        let body = withoutExistingExtends;
        let loadMatch = body.match(/^\s*{% load [^%]+ %}\s*/i);

        while (loadMatch) {
            loadTags.push(loadMatch[0].trim());
            body = body.slice(loadMatch[0].length).trim();
            loadMatch = body.match(/^\s*{% load [^%]+ %}\s*/i);
        }

        if (/{%\s*block\s+main\s*%}/i.test(body)) {
            return [
                extendsTag,
                loadTags.join("\n"),
                body,
            ].filter(Boolean).join("\n\n") + "\n";
        }

        return [
            extendsTag,
            loadTags.join("\n"),
            "{% block main %}",
            body,
            "{% endblock %}",
        ].filter(Boolean).join("\n\n") + "\n";
    }

    function loadThemeFileCode(fileKey) {
        let requestUrl = "";

        if (textarea.dataset.sourceFileCodeUrl) {
            requestUrl = textarea.dataset.sourceFileCodeUrl +
                "?theme_id=" + encodeURIComponent(getSelectedThemeId()) +
                "&file=" + encodeURIComponent(fileKey);
        } else if (textarea.dataset.fileCodeUrl) {
            requestUrl = textarea.dataset.fileCodeUrl +
                "?file=" + encodeURIComponent(fileKey);
        }

        if (!requestUrl) {
            return Promise.resolve({code: ""});
        }

        return editorFetch(requestUrl).then(response => response.json());
    }

    if (textarea.dataset.sourceFileCodeUrl || textarea.dataset.fileCodeUrl) {
        const sourceGroup = createGroup("Source HTML Files");
        const loadButton = createButton("Load file", function () {
            openChoiceModal(
                "Load HTML file",
                getFilesForSelectedTheme(),
                function (file) {
                    return file.name || (file.key + ".html");
                },
                function (file) {
                    loadThemeFileCode(file.key)
                        .then(data => {
                            editor.setValue(data.code || "");
                            editor.refresh();
                        })
                        .catch(error => {
                            console.error(error);
                            alert("File loading failed.");
                        });
                }
            );
        });
        const insertButton = createButton("Insert file", function () {
            openChoiceModal(
                "Insert HTML file",
                getFilesForSelectedTheme(),
                function (file) {
                    return file.name || (file.key + ".html");
                },
                function (file) {
                    loadThemeFileCode(file.key)
                        .then(data => {
                            editor.replaceSelection(data.code || "");
                            editor.focus();
                            editor.refresh();
                        })
                        .catch(error => {
                            console.error(error);
                            alert("File loading failed.");
                        });
                }
            );
        });

        sourceGroup.actions.appendChild(loadButton);
        sourceGroup.actions.appendChild(insertButton);
        sourceGroup.actions.appendChild(
            createButton("Asset browser", openAssetBrowser)
        );
        toolbar.appendChild(sourceGroup.group);
    }

    function openExtendsTemplateModal() {
        openChoiceModal(
            "Choose base template",
            getBaseTemplatesForSelectedTheme(),
            function (template) {
                return template.name || template.slug;
            },
            function (template) {
                editor.setValue(
                    buildExtendsTemplate(editor.getValue(), template.extends)
                );
                editor.focus();
                editor.refresh();
            }
        );
    }

    const tagsGroup = createGroup("Django Template Tags");

    [
        ["Load static", "{% load static %}"],
        ["Load i18n", "{% load i18n %}"],
        ["Load compress", "{% load compress %}"],
        ["Load comments", "{% load comments %}"],
        ["Current language", "{% get_current_language as LANGUAGE_CODE %}"],
        ["Language BIDI", "{% get_current_language_bidi as LANGUAGE_BIDI %}"],
        ["Variable", "{{ variable }}"],
        ["URL", "{% url 'app:view' %}"],
        ["Trans", "{% trans 'Text' %}"],
        ["If", "{% if variable %}\n\n{% endif %}"],
        ["For", "{% for item in items %}\n\n{% endfor %}"],
    ].forEach(function (item) {
        tagsGroup.actions.appendChild(
            createButton(item[0], function () {
                insertTag(item[1]);
            })
        );
    });

    toolbar.appendChild(tagsGroup.group);

    const siteLinksGroup = createGroup("Site Settings Links");

    siteLinksGroup.actions.appendChild(
        createButton("CMS link", openCmsLinkModal)
    );

    [
        ["Email", "{{ site_settings.contact_email }}", "mailto:", true],
        ["Phone", "{{ site_settings.contact_phone }}", "tel:", true],
        ["X", "{{ site_settings.x_url }}", "", false],
        ["Facebook", "{{ site_settings.facebook_url }}", "", false],
        ["Instagram", "{{ site_settings.instagram_url }}", "", false],
        ["LinkedIn", "{{ site_settings.linkedin_url }}", "", false],
        ["YouTube", "{{ site_settings.youtube_url }}", "", false],
        ["TikTok", "{{ site_settings.tiktok_url }}", "", false],
        ["Telegram", "{{ site_settings.telegram_url }}", "", false],
        ["WhatsApp", "{{ site_settings.whatsapp_url }}", "", false],
    ].forEach(function (item) {
        siteLinksGroup.actions.appendChild(
            createButton(item[0], function () {
                replaceSelectedAnchor(item[0], item[1], {
                    prefix: item[2],
                    replaceText: item[3],
                });
            })
        );
    });

    toolbar.appendChild(siteLinksGroup.group);

    const actionsGroup = createGroup("Template Actions");
    actionsGroup.actions.appendChild(
        createButton("Extends", openExtendsTemplateModal)
    );

    actionsGroup.actions.appendChild(
        createButton("Template components", openTemplateComponents)
    );

    const addIncludeButton = createButton("Add include", function () {
        openChoiceModal(
            "Add include block",
            getIncludeBlocksForSelectedTheme(),
            function (includeBlock) {
                return includeBlock.name || includeBlock.slug;
            },
            function (includeBlock) {
                editor.replaceSelection(includeBlock.include + "\n");
                editor.focus();
                editor.refresh();
            }
        );
    });

    actionsGroup.actions.appendChild(
        createButton("Replace static files", function () {
            if (!textarea.dataset.convertStaticUrl) {
                alert("Please save the template before using this action.");
                return;
            }

            const formData = new FormData();
            formData.append("code", editor.getValue());

            editorFetch(textarea.dataset.convertStaticUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: formData,
            })
                .then(response => response.json())
                .then(data => {
                    editor.setValue(data.code || "");
                    editor.refresh();
                })
                .catch(error => {
                    console.error(error);
                    alert("Static path conversion failed.");
                });
        })
    );

    actionsGroup.actions.appendChild(
        createButton("Search & replace", searchReplace.open)
    );

    actionsGroup.actions.appendChild(
        createButton("Format", formatTemplateCode)
    );

    actionsGroup.actions.appendChild(
        createButton("Normalize SEO head", normalizeSeoHead)
    );

    actionsGroup.actions.appendChild(
        createButton("Check template loads", analyzeTemplateLoads)
    );

    actionsGroup.actions.appendChild(
        createButton("Extract include", function () {
            if (!textarea.dataset.extractIncludeUrl) {
                alert("Please save the template before using this action.");
                return;
            }

            const selectedCode = editor.getSelection();

            if (!selectedCode.trim()) {
                alert("Please select the code block you want to extract.");
                return;
            }

            const blockName = prompt("Enter include block name:");

            if (!blockName || !blockName.trim()) {
                return;
            }

            const formData = new FormData();
            formData.append("selected_code", selectedCode);
            formData.append("name", blockName.trim());

            editorFetch(textarea.dataset.extractIncludeUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: formData,
            })
                .then(response => response.json())
                .then(data => {
                    if (data.include) {
                        editor.replaceSelection(data.include);
                        editor.focus();
                        editor.refresh();
                    } else {
                        alert(data.error || "Include extraction failed.");
                    }
                })
                .catch(error => {
                    console.error(error);
                    alert("Include extraction failed.");
                });
        })
    );

    actionsGroup.actions.appendChild(addIncludeButton);

    actionsGroup.actions.appendChild(
        createButton("Extract page block", function () {
            if (!textarea.dataset.extractPageBlockUrl) {
                alert("Please save the template before using this action.");
                return;
            }

            const selectedCode = editor.getSelection();

            if (!selectedCode.trim()) {
                alert("Please select the code block you want to extract.");
                return;
            }

            const templateName = prompt("Enter child template name:");

            if (!templateName || !templateName.trim()) {
                return;
            }

            const formData = new FormData();
            formData.append("selected_code", selectedCode);
            formData.append("name", templateName.trim());

            editorFetch(textarea.dataset.extractPageBlockUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: formData,
            })
                .then(response => response.json())
                .then(data => {
                    if (data.block) {
                        editor.replaceSelection(data.block);
                        editor.focus();
                        editor.refresh();
                    } else {
                        alert(data.error || "Page block extraction failed.");
                    }
                })
                .catch(error => {
                    console.error(error);
                    alert("Page block extraction failed.");
                });
        })
    );

    actionsGroup.actions.appendChild(
        createButton("Add page block", function () {
            editor.replaceSelection("{% block main %}{% endblock %}");
            editor.focus();
            editor.refresh();
        })
    );

    toolbar.appendChild(actionsGroup.group);

    const historyGroup = createGroup("Version History");
    historyGroup.actions.appendChild(
        createButton("Version history", openVersionHistory)
    );
    toolbar.appendChild(historyGroup.group);

    const aiGroup = createGroup("AI Template Builder");
    aiGroup.actions.appendChild(
        createButton("Generate image", function () {
            const imageSelection = getExpandedImageSelection();

            if (!imageSelection.code.trim()) {
                alert("Select an image path, a static tag, or an img tag.");
                return;
            }

            const imagePrompt = window.prompt(
                "Describe the image you want to generate.\nExample: A modern Ukrainian web studio team in a bright office, realistic photography."
            );

            if (!imagePrompt || !imagePrompt.trim()) {
                return;
            }

            runAiAction("generate_image", {
                image_prompt: imagePrompt.trim(),
            }, imageSelection);
        })
    );

    aiGroup.actions.appendChild(
        createButton("Generate text", function () {
            const selectedText = editor.getSelection();

            if (!selectedText.trim()) {
                alert("Select the text you want to replace.");
                return;
            }

            const textPrompt = window.prompt(
                "Describe the new text: language, subject, style and size.\nExample: Ukrainian, about our web studio, friendly tone, about 500 characters."
            );

            if (!textPrompt || !textPrompt.trim()) {
                return;
            }

            runAiAction("generate_text", {
                text_prompt: textPrompt.trim(),
            });
        })
    );

    aiGroup.actions.appendChild(
        createButton("Generate HTML", function () {
            const selectedCode = editor.getSelection();

            if (!selectedCode.trim()) {
                alert("Select the HTML or Django template code you want to edit.");
                return;
            }

            const htmlPrompt = window.prompt(
                "Describe how to change the selected code.\nExamples: make two Bootstrap columns; add a Bootstrap modal; preserve existing classes."
            );

            if (!htmlPrompt || !htmlPrompt.trim()) {
                return;
            }

            runAiAction("generate_html", {
                html_prompt: htmlPrompt.trim(),
            });
        })
    );

    aiGroup.actions.appendChild(
        createButton("Add AI assistant", function () {
            insertTag('{% include "includes/ai_chat_widget.html" %}');
        })
    );

    aiGroup.actions.appendChild(
        createButton("Convert category children list", openBlogCategoryChildrenModal)
    );

    [
        ["Convert to latest blog articles", "latest_blog_articles"],
        ["Convert Breadcrumbs", "breadcrumbs"],
        ["Convert Pagination", "pagination"],
        ["Convert Subscription", "subscription"],
        ["Convert Contact form", "contact_form"],
        ["Convert Comments", "comments"],
    ].forEach(function (item) {
        aiGroup.actions.appendChild(
            createButton(item[0], function () {
                const selectedCode = editor.getSelection();

                if (!selectedCode.trim()) {
                    alert("Select the HTML block you want to convert.");
                    return;
                }

                runAiAction("convert_component", {
                    component_type: item[1],
                });
            })
        );
    });

    [
        [
            "Convert language switcher",
            "Convert selected language switcher to Django i18n code with working language URLs. Keep layout and classes.",
        ],
        [
            "Add translations",
            "Wrap selected code with Django trans tags where needed. Keep HTML and classes.",
        ],
    ].forEach(function (item) {
        aiGroup.actions.appendChild(
            createButton(item[0], function () {
                runAiAction(item[1]);
            })
        );
    });

    toolbar.appendChild(aiGroup.group);
    buildToolbarTabs(toolbar);
    const editorShell = document.createElement("div");
    editorShell.className = "template-code-editor-shell";
    createFullscreenToggle(editorShell, toolbar, editor);

    const wrapper = editor.getWrapperElement();
    wrapper.parentNode.insertBefore(editorShell, wrapper);
    editorShell.appendChild(toolbar);
    editorShell.appendChild(wrapper);
    wrapper.parentNode.insertBefore(searchReplace.element, wrapper);
});
