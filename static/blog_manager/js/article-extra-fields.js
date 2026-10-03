(function () {
    "use strict";

    var choiceTypes = {
        select: true,
        multiselect: true,
        radio: true,
    };

    function parseJson(value) {
        if (!value) {
            return {};
        }

        try {
            return JSON.parse(value);
        } catch (_error) {
            return {};
        }
    }

    function createHelpText(text) {
        if (!text) {
            return null;
        }

        var help = document.createElement("div");
        help.className = "article-extra-field-help";
        help.textContent = text;
        return help;
    }

    function createTextInput(field, value) {
        var input = document.createElement("input");
        var type = field.type === "hidden" ? "hidden" : field.type;

        input.type = type === "textarea" ? "text" : type;
        input.value = value == null ? field.default || "" : String(value);
        input.placeholder = field.placeholder || "";
        input.required = field.required === true;
        input.dataset.articleExtraField = field.name;
        return input;
    }

    function createTextarea(field, value) {
        var textarea = document.createElement("textarea");
        textarea.rows = 4;
        textarea.value = value == null ? field.default || "" : String(value);
        textarea.placeholder = field.placeholder || "";
        textarea.required = field.required === true;
        textarea.dataset.articleExtraField = field.name;
        return textarea;
    }

    function createSelect(field, value) {
        var select = document.createElement("select");
        select.required = field.required === true;
        select.dataset.articleExtraField = field.name;

        if (field.type === "multiselect") {
            select.multiple = true;
        } else {
            var emptyOption = document.createElement("option");
            emptyOption.value = "";
            emptyOption.textContent = "---------";
            select.appendChild(emptyOption);
        }

        (field.choices || []).forEach(function (choice) {
            var option = document.createElement("option");
            option.value = choice;
            option.textContent = choice;

            if (field.type === "multiselect") {
                option.selected = Array.isArray(value) && value.indexOf(choice) !== -1;
            } else {
                option.selected = value === choice || (!value && field.default === choice);
            }

            select.appendChild(option);
        });

        return select;
    }

    function createCheckbox(field, value) {
        var wrapper = document.createElement("label");
        var input = document.createElement("input");
        var checkboxValue = Array.isArray(field.choices) && field.choices.length
            ? field.choices[0]
            : "true";

        input.type = "checkbox";
        input.value = checkboxValue;
        input.checked = value === true
            || value === "true"
            || value === checkboxValue
            || (!value && field.default === checkboxValue);
        input.required = field.required === true;
        input.dataset.articleExtraField = field.name;

        wrapper.className = "article-extra-checkbox";
        wrapper.appendChild(input);

        if (Array.isArray(field.choices) && field.choices.length) {
            wrapper.appendChild(document.createTextNode(field.choices[0]));
        }

        return wrapper;
    }

    function createRadioGroup(field, value) {
        var wrapper = document.createElement("div");
        wrapper.className = "article-extra-radio-group";
        wrapper.dataset.articleExtraField = field.name;

        (field.choices || []).forEach(function (choice, index) {
            var label = document.createElement("label");
            var input = document.createElement("input");

            input.type = "radio";
            input.name = "article_extra_" + field.name;
            input.value = choice;
            input.required = field.required === true;
            input.checked = value === choice || (!value && field.default === choice);

            label.appendChild(input);
            label.appendChild(document.createTextNode(choice));
            wrapper.appendChild(label);

            if (!value && !field.default && index === 0 && field.required === true) {
                input.checked = true;
            }
        });

        return wrapper;
    }

    function createFieldControl(field, value) {
        if (field.type === "textarea") {
            return createTextarea(field, value);
        }

        if (field.type === "checkbox") {
            return createCheckbox(field, value);
        }

        if (field.type === "radio") {
            return createRadioGroup(field, value);
        }

        if (field.type === "select" || field.type === "multiselect") {
            return createSelect(field, value);
        }

        return createTextInput(field, value);
    }

    function getControlValue(control, field) {
        if (field.type === "checkbox") {
            var checkbox = control.matches("input")
                ? control
                : control.querySelector("input");

            if (!checkbox || !checkbox.checked) {
                return "";
            }

            return checkbox.value || true;
        }

        if (field.type === "multiselect") {
            return Array.from(control.selectedOptions).map(function (option) {
                return option.value;
            });
        }

        if (field.type === "radio") {
            var checked = control.querySelector("input:checked");
            return checked ? checked.value : "";
        }

        if (field.type === "number") {
            return control.value === "" ? "" : control.value;
        }

        return control.value;
    }

    function initialize() {
        var category = document.getElementById("id_category");
        var hidden = document.querySelector("input.article-extra-fields-data");
        var container = document.querySelector(".article-extra-fields-form");

        if (!category || !hidden || !container) {
            return;
        }

        var schemaUrl = hidden.dataset.schemaUrl;
        var currentValues = parseJson(hidden.value);
        var currentFields = [];

        function syncHidden() {
            var data = {};

            currentFields.forEach(function (field) {
                var control = container.querySelector('[data-article-extra-field="' + field.name + '"]');

                if (!control) {
                    return;
                }

                data[field.name] = getControlValue(control, field);
            });

            hidden.value = JSON.stringify(data);
            currentValues = data;
        }

        function renderFields(fields) {
            container.innerHTML = "";
            currentFields = fields;

            if (!fields.length) {
                container.classList.add("is-empty");
                container.textContent = container.dataset.emptyMessage || "";
                hidden.value = "{}";
                currentValues = {};
                return;
            }

            container.classList.remove("is-empty");

            fields.forEach(function (field) {
                if (!field || !field.name || !field.type) {
                    return;
                }

                if (field.type === "file" || (choiceTypes[field.type] && !Array.isArray(field.choices))) {
                    return;
                }

                var row = document.createElement("div");
                var label = document.createElement("label");
                var value = Object.prototype.hasOwnProperty.call(currentValues, field.name)
                    ? currentValues[field.name]
                    : field.default || "";
                var control = createFieldControl(field, value);
                var help = createHelpText(field.help_text);

                row.className = "article-extra-field";
                label.textContent = field.label;

                if (field.required) {
                    var required = document.createElement("span");
                    required.className = "article-extra-field-required";
                    required.textContent = " *";
                    label.appendChild(required);
                }

                row.appendChild(label);
                row.appendChild(control);

                if (help) {
                    row.appendChild(help);
                }

                container.appendChild(row);
            });

            container.querySelectorAll("input, textarea, select").forEach(function (control) {
                control.addEventListener("change", syncHidden);
                control.addEventListener("input", syncHidden);
            });
            syncHidden();
        }

        function loadSchema() {
            var categoryId = category.value;

            if (!categoryId || !schemaUrl) {
                renderFields([]);
                return;
            }

            fetch(schemaUrl + "?category_id=" + encodeURIComponent(categoryId), {
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            })
                .then(function (response) {
                    return response.json();
                })
                .then(function (data) {
                    renderFields(Array.isArray(data.fields) ? data.fields : []);
                })
                .catch(function () {
                    renderFields([]);
                });
        }

        hidden.form && hidden.form.addEventListener("submit", syncHidden);
        category.addEventListener("change", loadSchema);
        loadSchema();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize);
    } else {
        initialize();
    }
})();
