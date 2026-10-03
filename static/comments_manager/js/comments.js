(function () {
    "use strict";

    function isCommentForm(form) {
        const action = form.getAttribute("action") || "";
        return action.indexOf("/comments/post/") !== -1;
    }

    function setSubmitting(form, isSubmitting) {
        const submitButton = form.querySelector(
            'button[type="submit"], input[type="submit"]'
        );

        if (submitButton) {
            submitButton.disabled = isSubmitting;
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("form").forEach(function (form) {
            if (!isCommentForm(form)) {
                return;
            }

            form.querySelectorAll(
                '.submit-preview, input[type="submit"][name="preview"]'
            ).forEach(function (button) {
                button.remove();
            });
        });
    });

    document.addEventListener("submit", function (event) {
        const form = event.target;

        if (!(form instanceof HTMLFormElement) || !isCommentForm(form)) {
            return;
        }

        event.preventDefault();
        setSubmitting(form, true);

        fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
            credentials: "same-origin",
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Comment could not be added.");
                }

                if (!response.redirected) {
                    throw new Error("Please check the comment form fields.");
                }

                alert("Comment added.");
                window.location.reload();
            })
            .catch(function (error) {
                alert(error.message || "Comment could not be added.");
                setSubmitting(form, false);
            });
    });
})();
