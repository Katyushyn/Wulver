(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var textarea = document.querySelector("textarea.codemirror-authentication-template");

        if (!textarea || typeof window.CodeMirror === "undefined") {
            return;
        }

        var editor = window.CodeMirror.fromTextArea(textarea, {
            mode: "htmlmixed",
            theme: "material-darker",
            lineNumbers: true,
            lineWrapping: false,
            indentUnit: 4,
            tabSize: 4,
            indentWithTabs: false,
        });

        editor.setSize("100%", "70vh");
        editor.on("change", function () {
            editor.save();
        });
    });
})();
