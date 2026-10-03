(function () {
    "use strict";
    function initialize() {
        var textarea = document.querySelector("textarea.codemirror-comment-css");
        if (!textarea || typeof window.CodeMirror === "undefined") return;
        var editor = window.CodeMirror.fromTextArea(textarea, {
            mode: "css", theme: "material-darker", lineNumbers: true, lineWrapping: false,
            indentUnit: 4, tabSize: 4, indentWithTabs: false,
            matchBrackets: true, autoCloseBrackets: true
        });
        editor.setSize("100%", "620px");
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize);
    else initialize();
})();
