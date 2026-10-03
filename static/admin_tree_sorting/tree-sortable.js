(function () {
    "use strict";

    const pendingSaves = new Set();

    function label(message) {
        return typeof window.gettext === "function" ? window.gettext(message) : message;
    }

    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(";") : [];
        for (const cookieValue of cookies) {
            const cookie = cookieValue.trim();
            if (cookie.startsWith(name + "=")) {
                return decodeURIComponent(cookie.slice(name.length + 1));
            }
        }
        return "";
    }

    function serializeList(list) {
        return Array.from(list.children)
            .filter((item) => item.classList.contains("admin-tree-item"))
            .map((item) => {
                const childList = Array.from(item.children).find(
                    (child) => child.classList && child.classList.contains("admin-tree-list")
                );
                return {
                    id: Number(item.dataset.id),
                    children: childList ? serializeList(childList) : [],
                };
            });
    }

    function setStatus(container, message, state) {
        const modal = container.closest("[data-tree-modal]");
        const status = modal ? modal.querySelector("[data-tree-status]") : null;
        if (!status) {
            return;
        }
        status.textContent = label(message);
        status.dataset.state = state || "";
    }

    async function saveTree(root) {
        const container = root.closest("[data-tree-sorter]");
        setStatus(container, "Saving...", "saving");

        const response = await fetch(root.dataset.saveUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({
                scope_id: root.dataset.scopeId || null,
                tree: serializeList(root),
            }),
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(data.error || "Could not save tree order.");
        }

        setStatus(container, "Saved", "saved");
        window.setTimeout(() => setStatus(container, "Ready", ""), 1500);
    }

    function queueSave(root) {
        const operation = saveTree(root)
            .catch((error) => {
                const container = root.closest("[data-tree-sorter]");
                setStatus(container, error.message, "error");
                window.setTimeout(() => window.location.reload(), 1400);
            })
            .finally(() => pendingSaves.delete(operation));

        pendingSaves.add(operation);
    }

    function initializeRoot(root) {
        const groupName = root.dataset.group;
        const lists = [root].concat(Array.from(root.querySelectorAll(".js-admin-tree-list")));

        lists.forEach(function (list) {
            Sortable.create(list, {
                group: groupName,
                animation: 160,
                handle: ".admin-tree-item__handle",
                draggable: ".admin-tree-item",
                fallbackOnBody: true,
                swapThreshold: 0.65,
                emptyInsertThreshold: 18,
                onEnd: () => queueSave(root),
            });
        });
    }

    function initializeModal(modal) {
        const openButton = document.querySelector("[data-tree-modal-open]");
        const closeButton = modal.querySelector("[data-tree-modal-close]");
        let reloadStarted = false;

        if (openButton) {
            openButton.addEventListener("click", () => modal.showModal());
        }
        if (closeButton) {
            closeButton.addEventListener("click", () => modal.close());
        }

        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                modal.close();
            }
        });

        modal.addEventListener("close", async () => {
            if (reloadStarted) {
                return;
            }
            reloadStarted = true;
            await Promise.allSettled(Array.from(pendingSaves));
            window.location.reload();
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const modal = document.querySelector("[data-tree-modal]");
        if (!modal) {
            return;
        }

        initializeModal(modal);

        if (typeof Sortable !== "undefined") {
            document.querySelectorAll(".js-admin-tree-root").forEach(initializeRoot);
        }
    });
})();
