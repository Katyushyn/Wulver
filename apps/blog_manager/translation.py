from modeltranslation.translator import TranslationOptions, register

from .models import Article, ArticleImage, Category, Tag


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = (
        "title",
        "seo_title",
        "description",
        "intro",
        "keywords",
    )


@register(Article)
class ArticleTranslationOptions(TranslationOptions):
    fields = (
        "title",
        "seo_title",
        "description",
        "intro",
        "body",
        "keywords",
    )


@register(Tag)
class TagTranslationOptions(TranslationOptions):
    fields = ("title",)


@register(ArticleImage)
class ArticleImageTranslationOptions(TranslationOptions):
    fields = ("alt_text",)
