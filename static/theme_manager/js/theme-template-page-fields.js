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
        const isChildrenPage = templateType.value === "parent_page";
        const isChildrenArticle = templateType.value === "parent_article";

        setFieldsetVisibility(pageFields, isChildrenPage);
        setFieldsetVisibility(articleFields, isChildrenArticle);
    }

    templateType.addEventListener("change", updateConditionalFieldsVisibility);
    updateConditionalFieldsVisibility();
});
