from modeltranslation.translator import TranslationOptions, register

from .models import CommentSettings


@register(CommentSettings)
class CommentSettingsTranslationOptions(TranslationOptions):
    fields = (
        "form_title",
        "comment_label",
        "comment_placeholder",
        "submit_text",
        "empty_text",
    )
