(function () {
    "use strict";

    function removeBrokenEditors(textarea) {
        var parent = textarea.parentNode;
        if (!parent) return;
        parent.querySelectorAll(":scope > .CodeMirror").forEach(function (element) {
            element.remove();
        });
        textarea.style.display = "";
        delete textarea.dataset.codeMirrorInitialized;
    }

    function initialize() {
        var textarea = document.querySelector("textarea.codemirror-comment-template");
        if (!textarea || textarea.dataset.codeMirrorInitialized === "true") return;
        if (typeof window.CodeMirror === "undefined") return;

        removeBrokenEditors(textarea);
        try {
            var editor = window.CodeMirror.fromTextArea(textarea, {
                mode: "htmlmixed",
                theme: "material-darker",
                lineNumbers: true,
                lineWrapping: false,
                indentUnit: 4,
                tabSize: 4,
                indentWithTabs: false,
                viewportMargin: 20
            });
            textarea.dataset.codeMirrorInitialized = "true";
            editor.setSize("100%", "680px");
            editor.setValue(textarea.value);
            editor.clearHistory();
            window.requestAnimationFrame(function () { editor.refresh(); });
        } catch (error) {
            removeBrokenEditors(textarea);
            console.error("Comment template editor could not start.", error);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize, {once: true});
    } else {
        initialize();
    }
})();
