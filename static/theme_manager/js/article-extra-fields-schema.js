(function () {
    "use strict";

    function label(message) {
        return typeof window.gettext === "function" ? window.gettext(message) : message;
    }

    function getJsonErrorLine(message, code) {
        var positionMatch = /position\s+(\d+)/i.exec(message);

        if (!positionMatch) {
            return null;
        }

        var position = parseInt(positionMatch[1], 10);
        var beforeError = code.slice(0, position);

        return beforeError.split("\n").length - 1;
    }

    function initialize() {
        var textarea = document.querySelector("textarea.codemirror-article-extra-fields-schema");

        if (!textarea || typeof window.CodeMirror === "undefined") {
            return;
        }

        var errorMessage = document.createElement("div");
        errorMessage.className = "article-extra-fields-json-error";
        errorMessage.hidden = true;

        textarea.insertAdjacentElement("afterend", errorMessage);

        var editor = window.CodeMirror.fromTextArea(textarea, {
            mode: {
                name: "javascript",
                json: true,
            },
            theme: "material-darker",
            lineNumbers: true,
            lineWrapping: true,
            styleActiveLine: true,
            matchBrackets: true,
            autoCloseBrackets: true,
            indentUnit: 2,
            tabSize: 2,
            indentWithTabs: false,
        });
        var errorLineHandle = null;

        editor.setSize("100%", "260px");

        function clearErrorLine() {
            if (errorLineHandle) {
                editor.removeLineClass(errorLineHandle, "background", "cm-json-error-line");
                errorLineHandle = null;
            }
        }

        function validateJson() {
            var code = editor.getValue().trim();

            editor.save();
            clearErrorLine();

            if (!code) {
                errorMessage.hidden = true;
                errorMessage.textContent = "";
                textarea.setCustomValidity("");
                return true;
            }

            try {
                JSON.parse(code);
                errorMessage.hidden = true;
                errorMessage.textContent = "";
                textarea.setCustomValidity("");
                return true;
            } catch (error) {
                var line = getJsonErrorLine(error.message, code);

                if (line !== null) {
                    errorLineHandle = editor.addLineClass(line, "background", "cm-json-error-line");
                }

                errorMessage.hidden = false;
                errorMessage.textContent = label("JSON error:") + " " + error.message;
                textarea.setCustomValidity(errorMessage.textContent);
                return false;
            }
        }

        editor.on("change", validateJson);
        textarea.form && textarea.form.addEventListener("submit", function (event) {
            if (!validateJson()) {
                event.preventDefault();
                editor.focus();
            }
        });
        validateJson();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize);
    } else {
        initialize();
    }
})();
