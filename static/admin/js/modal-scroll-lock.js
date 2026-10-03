(function () {
    "use strict";

    var MODAL_SELECTOR = [
        ".template-code-modal-backdrop",
        ".article-content-images:not([hidden])",
        "dialog[open]",
        ".modal.show",
        '[role="dialog"][aria-modal="true"]',
    ].join(",");
    var locked = false;
    var scheduled = false;
    var originalStyles = null;

    function captureProperty(element, property) {
        return {
            value: element.style.getPropertyValue(property),
            priority: element.style.getPropertyPriority(property),
        };
    }

    function restoreProperty(element, property, saved) {
        if (saved.value) {
            element.style.setProperty(property, saved.value, saved.priority);
        } else {
            element.style.removeProperty(property);
        }
    }

    function isVisibleModal(element) {
        if (element.hidden || element.getAttribute("aria-hidden") === "true") {
            return false;
        }
        if (element.tagName === "DIALOG" && !element.open) {
            return false;
        }
        return element.getClientRects().length > 0;
    }

    function hasOpenModal() {
        return Array.from(document.querySelectorAll(MODAL_SELECTOR)).some(isVisibleModal);
    }

    function lockPageScroll() {
        if (locked || !document.body) {
            return;
        }
        var root = document.documentElement;
        var body = document.body;
        var scrollbarWidth = Math.max(0, window.innerWidth - root.clientWidth);
        var bodyPaddingRight = parseFloat(window.getComputedStyle(body).paddingRight) || 0;

        originalStyles = {
            rootOverflow: captureProperty(root, "overflow"),
            rootOverscroll: captureProperty(root, "overscroll-behavior"),
            bodyOverflow: captureProperty(body, "overflow"),
            bodyOverscroll: captureProperty(body, "overscroll-behavior"),
            bodyPaddingRight: captureProperty(body, "padding-right"),
        };

        root.style.setProperty("overflow", "hidden", "important");
        root.style.setProperty("overscroll-behavior", "none", "important");
        body.style.setProperty("overflow", "hidden", "important");
        body.style.setProperty("overscroll-behavior", "none", "important");
        if (scrollbarWidth) {
            body.style.setProperty(
                "padding-right",
                (bodyPaddingRight + scrollbarWidth) + "px",
                "important"
            );
        }
        root.classList.add("wulver-admin-modal-open");
        locked = true;
    }

    function unlockPageScroll() {
        if (!locked || !originalStyles || !document.body) {
            return;
        }
        var root = document.documentElement;
        var body = document.body;

        restoreProperty(root, "overflow", originalStyles.rootOverflow);
        restoreProperty(root, "overscroll-behavior", originalStyles.rootOverscroll);
        restoreProperty(body, "overflow", originalStyles.bodyOverflow);
        restoreProperty(body, "overscroll-behavior", originalStyles.bodyOverscroll);
        restoreProperty(body, "padding-right", originalStyles.bodyPaddingRight);
        root.classList.remove("wulver-admin-modal-open");
        originalStyles = null;
        locked = false;
    }

    function refresh() {
        scheduled = false;
        if (hasOpenModal()) {
            lockPageScroll();
        } else {
            unlockPageScroll();
        }
    }

    function scheduleRefresh() {
        if (scheduled) {
            return;
        }
        scheduled = true;
        window.requestAnimationFrame(refresh);
    }

    function initialize() {
        var observer = new MutationObserver(scheduleRefresh);
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["class", "hidden", "open", "aria-hidden", "aria-modal"],
        });
        document.addEventListener("toggle", scheduleRefresh, true);
        document.addEventListener("close", scheduleRefresh, true);
        window.addEventListener("pageshow", scheduleRefresh);
        scheduleRefresh();

        window.WulverAdminModalScrollLock = {
            refresh: scheduleRefresh,
        };
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize, {once: true});
    } else {
        initialize();
    }
})();
