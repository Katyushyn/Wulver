(function () {
    "use strict";

    var storageKey = "wulver:admin:save-and-continue-scroll";
    var maximumAge = 60 * 1000;
    var pendingEditorPositions = [];

    function captureEditorPositions() {
        return Array.from(
            document.querySelectorAll(
                "textarea.codemirror-template-html, "
                + "textarea.codemirror-article-body"
            )
        ).map(function (textarea) {
            var editor = textarea._wulverCodeMirror;
            if (!editor || typeof editor.getScrollInfo !== "function") {
                return null;
            }
            var scroll = editor.getScrollInfo();
            var cursor = typeof editor.getCursor === "function"
                ? editor.getCursor()
                : null;
            return {
                name: textarea.name || "",
                id: textarea.id || "",
                left: scroll.left || 0,
                top: scroll.top || 0,
                cursor: cursor,
            };
        }).filter(Boolean);
    }

    function readStoredPosition() {
        try {
            var value = window.sessionStorage.getItem(storageKey);
            window.sessionStorage.removeItem(storageKey);
            return value ? JSON.parse(value) : null;
        } catch (error) {
            return null;
        }
    }

    function storePosition() {
        try {
            window.sessionStorage.setItem(storageKey, JSON.stringify({
                x: window.scrollX || 0,
                y: window.scrollY || 0,
                createdAt: Date.now(),
                editors: captureEditorPositions(),
            }));
        } catch (error) {
            // Saving must continue even when browser storage is unavailable.
        }
    }

    function isContinueButton(element) {
        return Boolean(
            element
            && element.matches
            && element.matches('[name="_continue"]')
        );
    }

    function restorePosition(position) {
        if (
            !position
            || !document.body
            || !document.body.classList.contains("change-form")
            || Date.now() - Number(position.createdAt || 0) > maximumAge
        ) {
            return;
        }

        if ("scrollRestoration" in window.history) {
            window.history.scrollRestoration = "manual";
        }

        var x = Math.max(0, Number(position.x) || 0);
        var y = Math.max(0, Number(position.y) || 0);
        pendingEditorPositions = Array.isArray(position.editors)
            ? position.editors
            : [];
        var apply = function () {
            window.scrollTo(x, y);
        };

        apply();
        window.requestAnimationFrame(apply);
        window.addEventListener("load", apply, {once: true});
        window.setTimeout(apply, 100);
        window.setTimeout(apply, 400);

        document.querySelectorAll(
            "textarea.codemirror-template-html, "
            + "textarea.codemirror-article-body"
        ).forEach(
            function (textarea) {
                if (textarea._wulverCodeMirror) {
                    restoreEditorPosition(textarea, textarea._wulverCodeMirror);
                }
            }
        );
    }

    function restoreEditorPosition(textarea, editor) {
        var position = pendingEditorPositions.find(function (item) {
            return (
                item.name && item.name === (textarea.name || "")
            ) || (
                item.id && item.id === (textarea.id || "")
            );
        });
        if (!position || !editor || typeof editor.scrollTo !== "function") {
            return;
        }

        var apply = function () {
            if (typeof editor.refresh === "function") {
                editor.refresh();
            }
            editor.scrollTo(
                Math.max(0, Number(position.left) || 0),
                Math.max(0, Number(position.top) || 0)
            );
        };
        if (position.cursor && typeof editor.setCursor === "function") {
            editor.setCursor(position.cursor);
        }
        apply();
        window.requestAnimationFrame(apply);
        window.setTimeout(apply, 100);
        window.setTimeout(apply, 400);
    }

    document.addEventListener("submit", function (event) {
        var submitter = event.submitter || document.activeElement;
        if (isContinueButton(submitter)) {
            storePosition();
        }
    }, true);

    document.addEventListener("click", function (event) {
        var button = event.target && event.target.closest
            ? event.target.closest('[name="_continue"]')
            : null;
        if (button) {
            storePosition();
        }
    }, true);

    document.addEventListener("wulver:code-editor-ready", function (event) {
        var detail = event.detail || {};
        if (detail.textarea && detail.editor) {
            restoreEditorPosition(detail.textarea, detail.editor);
        }
    });

    var storedPosition = readStoredPosition();
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            restorePosition(storedPosition);
        }, {once: true});
    } else {
        restorePosition(storedPosition);
    }
})();
