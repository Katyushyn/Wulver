from modeltranslation.translator import TranslationOptions, register

from .models import AuthenticationEmailTemplate


@register(AuthenticationEmailTemplate)
class AuthenticationEmailTemplateTranslationOptions(TranslationOptions):
    fields = (
        "subject",
        "message",
    )
