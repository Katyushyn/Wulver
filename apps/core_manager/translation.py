from modeltranslation.translator import TranslationOptions, register

from .models import Page, SiteSettings, URLLink


@register(Page)
class PageTranslationOptions(TranslationOptions):
    fields = (
        "title",
        "description",
        "keywords",
    )


@register(SiteSettings)
class SiteSettingsTranslationOptions(TranslationOptions):
    fields = (
        "site_name",
        "title",
        "description",
        "default_image_alt",
        "author_name",
        "og_site_name",
        "organization_name",
        "person_name",
        "person_job_title",
        "maintenance_message",
    )


@register(URLLink)
class URLLinkTranslationOptions(TranslationOptions):
    fields = ("title",)
