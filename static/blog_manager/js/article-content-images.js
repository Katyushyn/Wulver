(function () {
    "use strict";

    var config = null;
    var modal = null;
    var gallery = null;
    var status = null;
    var activeInputName = "";

    function label(message) {
        return typeof window.gettext === "function" ? window.gettext(message) : message;
    }

    function csrfToken() {
        var input = document.querySelector("input[name='csrfmiddlewaretoken']");
        return input ? input.value : "";
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function buildImage(image, alt) {
        var dimensions = image.width && image.height
            ? " width=\"" + image.width + "\" height=\"" + image.height + "\""
            : "";
        var html = "<img class=\"article-content-image\" src=\"" + escapeHtml(image.url) + "\" alt=\"";
        html += escapeHtml(alt) + "\"" + dimensions;
        return html + " loading=\"lazy\" decoding=\"async\" style=\"display:block;width:auto;max-width:100%;height:auto;margin:2rem auto;\">";
    }

    function setStatus(message, isError) {
        status.textContent = message || "";
        status.classList.toggle("is-error", Boolean(isError));
    }

    async function requestImages(formData) {
        var options = {
            method: formData ? "POST" : "GET",
            headers: {"X-Requested-With": "XMLHttpRequest"},
        };
        if (formData) {
            options.body = formData;
            options.headers["X-CSRFToken"] = csrfToken();
        }

        var response = await fetch(config.dataset.url, options);
        var payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || label("Could not process article images."));
        }
        return payload;
    }

    function actionButton(text, className) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "article-content-images__action " + className;
        button.textContent = text;
        return button;
    }

    function renderImages(images) {
        gallery.replaceChildren();
        if (!images.length) {
            var empty = document.createElement("p");
            empty.className = "article-content-images__empty";
            empty.textContent = label("No content images have been uploaded yet.");
            gallery.appendChild(empty);
            return;
        }

        images.forEach(function (image) {
            var card = document.createElement("article");
            card.className = "article-content-images__card";

            var media = document.createElement("div");
            media.className = "article-content-images__media";

            var preview = document.createElement("img");
            preview.className = "article-content-images__preview";
            preview.src = image.url;
            preview.alt = image.alt || "";
            preview.loading = "lazy";
            media.appendChild(preview);

            card.appendChild(media);

            var details = document.createElement("div");
            details.className = "article-content-images__details";

            var info = document.createElement("div");
            info.className = "article-content-images__info";
            var meta = document.createElement("p");
            meta.className = "article-content-images__meta";
            meta.textContent = image.width + " × " + image.height + " · " + image.size_display;
            info.appendChild(meta);

            var imagePath = document.createElement("code");
            imagePath.className = "article-content-images__path";
            imagePath.textContent = image.url;
            imagePath.title = image.url;
            info.appendChild(imagePath);
            details.appendChild(info);

            var controls = document.createElement("div");
            controls.className = "article-content-images__controls";

            var altLabel = document.createElement("label");
            altLabel.textContent = label("Alt text");
            var altInput = document.createElement("input");
            altInput.type = "text";
            altInput.maxLength = 250;
            altInput.value = image.alt || "";
            altLabel.appendChild(altInput);
            controls.appendChild(altLabel);

            var actions = document.createElement("div");
            actions.className = "article-content-images__actions";
            var insertButton = actionButton(label("Insert"), "is-primary");
            var deleteButton = actionButton(label("Delete"), "is-danger");
            actions.appendChild(insertButton);
            actions.appendChild(deleteButton);
            controls.appendChild(actions);
            details.appendChild(controls);
            card.appendChild(details);
            gallery.appendChild(card);

            insertButton.addEventListener("click", function () {
                if (insertButton.disabled) {
                    return;
                }
                insertButton.disabled = true;
                document.dispatchEvent(new CustomEvent("wulver:insert-article-image", {
                    detail: {
                        inputName: activeInputName,
                        imageUrl: image.url,
                        width: image.width,
                        height: image.height,
                        html: buildImage(image, altInput.value.trim()),
                    },
                }));
                closeModal();
            });

            altInput.addEventListener("change", async function () {
                var previousAlt = image.alt || "";
                var nextAlt = altInput.value.trim();
                if (nextAlt === previousAlt) {
                    return;
                }

                var formData = new FormData();
                formData.append("action", "update");
                formData.append("image_id", image.id);
                formData.append("alt", nextAlt);
                formData.append("sort_order", image.sort_order || 0);
                try {
                    altInput.disabled = true;
                    setStatus(label("Saving image details..."), false);
                    await requestImages(formData);
                    image.alt = nextAlt;
                    preview.alt = nextAlt;
                    setStatus(label("Image details saved."), false);
                } catch (error) {
                    altInput.value = previousAlt;
                    setStatus(error.message, true);
                } finally {
                    altInput.disabled = false;
                }
            });

            deleteButton.addEventListener("click", async function () {
                if (!window.confirm(label("Delete this image? Existing article markup will not be removed."))) {
                    return;
                }
                var formData = new FormData();
                formData.append("action", "delete");
                formData.append("image_id", image.id);
                try {
                    setStatus(label("Deleting image..."), false);
                    var payload = await requestImages(formData);
                    renderImages(payload.images || []);
                    setStatus(label("Image deleted."), false);
                } catch (error) {
                    setStatus(error.message, true);
                }
            });
        });
    }

    function closeModal() {
        if (modal) {
            modal.hidden = true;
            document.body.classList.remove("article-content-images-open");
        }
    }

    function buildModal() {
        modal = document.createElement("div");
        modal.className = "article-content-images";
        modal.hidden = true;
        modal.innerHTML = [
            "<div class=\"article-content-images__backdrop\"></div>",
            "<section class=\"article-content-images__dialog\" role=\"dialog\" aria-modal=\"true\" aria-label=\"" + escapeHtml(label("Article images")) + "\">",
            "<header class=\"article-content-images__header\"><div><h2>" + escapeHtml(label("Article images")) + "</h2><p class=\"article-content-images__help\"></p></div><button type=\"button\" class=\"article-content-images__close\" aria-label=\"" + escapeHtml(label("Close")) + "\">×</button></header>",
            "<form class=\"article-content-images__upload\"><input type=\"file\" name=\"images\" accept=\"image/jpeg,image/png,image/webp,image/avif\" multiple required><button type=\"submit\">" + escapeHtml(label("Upload images")) + "</button></form>",
            "<p class=\"article-content-images__status\" aria-live=\"polite\"></p>",
            "<div class=\"article-content-images__gallery\"></div>",
            "</section>",
        ].join("");
        document.body.appendChild(modal);
        gallery = modal.querySelector(".article-content-images__gallery");
        status = modal.querySelector(".article-content-images__status");

        modal.querySelector(".article-content-images__backdrop").addEventListener("click", closeModal);
        modal.querySelector(".article-content-images__close").addEventListener("click", closeModal);
        modal.querySelector(".article-content-images__upload").addEventListener("submit", async function (event) {
            event.preventDefault();
            var fileInput = event.currentTarget.querySelector("input[type='file']");
            if (!fileInput.files.length) {
                return;
            }
            var formData = new FormData();
            formData.append("action", "upload");
            Array.from(fileInput.files).forEach(function (file) {
                formData.append("images", file);
            });
            try {
                setStatus(label("Converting images to AVIF..."), false);
                var payload = await requestImages(formData);
                renderImages(payload.images || []);
                fileInput.value = "";
                setStatus(label("Images uploaded."), false);
            } catch (error) {
                setStatus(error.message, true);
            }
        });
    }

    async function openModal(inputName) {
        config = document.querySelector(".article-content-images-config");
        if (!config || !config.dataset.url) {
            window.alert(
                config && config.dataset.unsavedMessage
                    ? config.dataset.unsavedMessage
                    : label("Save the article before uploading content images.")
            );
            return;
        }
        if (!modal) {
            buildModal();
        }
        activeInputName = inputName;
        modal.hidden = false;
        document.body.classList.add("article-content-images-open");
        setStatus(label("Loading images..."), false);
        try {
            var payload = await requestImages();
            modal.querySelector(".article-content-images__help").textContent = payload.upload_help || "";
            renderImages(payload.images || []);
            setStatus("", false);
        } catch (error) {
            setStatus(error.message, true);
        }
    }

    document.addEventListener("wulver:open-article-images", function (event) {
        openModal((event.detail || {}).inputName || "");
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && modal && !modal.hidden) {
            closeModal();
        }
    });
})();
