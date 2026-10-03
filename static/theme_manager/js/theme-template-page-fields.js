document.addEventListener("DOMContentLoaded", function () {
    const templateType = document.getElementById("id_template_type");
    const pageFields = document.querySelector("fieldset.theme-template-page-fields");
    const articleFields = document.querySelector("fieldset.theme-template-article-fields");

    if (!templateType) {
        return;
    }

    function setFieldsetVisibility(fieldset, isVisible) {
        if (!fieldset) {
            return;
        }

        fieldset.hidden = !isVisible;
        fieldset.style.display = isVisible ? "" : "none";
    }

    function updateConditionalFieldsVisibility() {
        const isParentPage = templateType.value === "parent_page";
        const isParentArticle = templateType.value === "parent_article";

        setFieldsetVisibility(pageFields, isParentPage);
        setFieldsetVisibility(articleFields, isParentArticle);
    }

    templateType.addEventListener("change", updateConditionalFieldsVisibility);
    updateConditionalFieldsVisibility();
});
