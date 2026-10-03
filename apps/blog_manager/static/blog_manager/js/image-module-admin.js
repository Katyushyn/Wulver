document.addEventListener("DOMContentLoaded", function () {
    function label(message) {
        return typeof window.gettext === "function" ? window.gettext(message) : message;
    }

    const manifestInput = document.getElementById("id_manifest_editor");
    const gallery = document.querySelector(".image-module-gallery[data-media-url]");
    const uploadInput = document.getElementById("id_uploads");

    if (!manifestInput || !gallery) {
        return;
    }

    let items = [];
    try {
        items = JSON.parse(manifestInput.value || "[]");
    } catch (error) {
        items = [];
    }

    const mediaUrl = gallery.dataset.mediaUrl.replace(/\/$/, "");

    function sync() {
        manifestInput.value = JSON.stringify(items);
    }

    function move(index, offset) {
        const target = index + offset;
        if (target < 0 || target >= items.length) {
            return;
        }
        const current = items[index];
        items[index] = items[target];
        items[target] = current;
        sync();
        render();
    }

    function actionButton(label, title, onClick) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "image-module-gallery-action";
        button.textContent = label;
        button.title = title;
        button.addEventListener("click", onClick);
        return button;
    }

    function render() {
        gallery.innerHTML = "";
        gallery.classList.toggle("is-empty", items.length === 0);
        if (!items.length) {
            gallery.textContent = label("No images uploaded yet.");
            return;
        }

        items.forEach(function (item, index) {
            const card = document.createElement("div");
            const details = document.createElement("div");
            const imageLink = document.createElement("a");
            const altLabel = document.createElement("label");
            const altInput = document.createElement("input");
            const activeLabel = document.createElement("label");
            const activeInput = document.createElement("input");
            const actions = document.createElement("div");

            card.className = "image-module-gallery-card";
            details.className = "image-module-gallery-details";
            const filePath = String(item.file || "").replace(/^\//, "");
            const imageUrl = mediaUrl + "/" + filePath;
            imageLink.className = "image-module-gallery-link";
            imageLink.href = imageUrl;
            imageLink.target = "_blank";
            imageLink.rel = "noopener noreferrer";
            imageLink.textContent = imageUrl;
            imageLink.title = label("Open") + " " + (item.name || filePath || "image") + " " + label("in a new tab");

            altLabel.className = "image-module-gallery-label";
            altLabel.textContent = label("Alt text");
            altInput.type = "text";
            altInput.className = "image-module-gallery-alt";
            altInput.maxLength = 250;
            altInput.value = item.alt || "";
            altInput.addEventListener("input", function () {
                item.alt = altInput.value;
                sync();
            });
            altLabel.appendChild(altInput);

            activeLabel.className = "image-module-gallery-active";
            activeInput.type = "checkbox";
            activeInput.checked = item.active !== false;
            activeInput.addEventListener("change", function () {
                item.active = activeInput.checked;
                sync();
            });
            activeLabel.appendChild(activeInput);
            activeLabel.appendChild(document.createTextNode(" " + label("Active")));

            actions.className = "image-module-gallery-actions";
            actions.appendChild(actionButton("↑", label("Move up"), function () {
                move(index, -1);
            }));
            actions.appendChild(actionButton("↓", label("Move down"), function () {
                move(index, 1);
            }));
            actions.appendChild(actionButton("×", label("Remove on save"), function () {
                if (!window.confirm(label("Remove this image when the module is saved?"))) {
                    return;
                }
                items.splice(index, 1);
                sync();
                render();
            }));

            details.appendChild(imageLink);
            details.appendChild(altLabel);
            details.appendChild(activeLabel);
            details.appendChild(actions);
            card.appendChild(details);
            gallery.appendChild(card);
        });
    }

    if (uploadInput) {
        uploadInput.addEventListener("change", function () {
            const selected = Array.from(uploadInput.files || []);
            uploadInput.title = selected.length
                ? selected.length + " " + label("image files selected")
                : "";
        });
    }

    sync();
    render();
});
