(function () {
    function initializeAdminHelp() {
        const dialog = document.querySelector("[data-admin-help-dialog]");
        if (!dialog || dialog.dataset.adminHelpReady === "true") {
            return;
        }

        dialog.dataset.adminHelpReady = "true";
        const openButtons = document.querySelectorAll("[data-admin-help-open]");
        const closeButtons = dialog.querySelectorAll("[data-admin-help-close]");

        openButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                if (typeof dialog.showModal === "function") {
                    dialog.showModal();
                } else {
                    dialog.setAttribute("open", "");
                }
            });
        });

        closeButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                if (typeof dialog.close === "function") {
                    dialog.close();
                } else {
                    dialog.removeAttribute("open");
                }
            });
        });

        dialog.addEventListener("click", function (event) {
            if (event.target === dialog) {
                dialog.close();
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeAdminHelp);
    } else {
        initializeAdminHelp();
    }
})();
