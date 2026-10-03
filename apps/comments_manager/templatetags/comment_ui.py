from django import template
from django.template import Template, TemplateSyntaxError
from django.utils.safestring import mark_safe

from apps.comments_manager.models import CommentSettings, CommentTemplate


register = template.Library()


@register.simple_tag
def comment_ui():
    return CommentSettings.get_solo()


@register.simple_tag(takes_context=True)
def render_comment_template(context, template_type):
    obj = CommentTemplate.objects.filter(template_type=template_type).first()
    if obj is None:
        return ""
    try:
        return mark_safe(Template(obj.code).render(context))
    except TemplateSyntaxError as error:
        return mark_safe(f"<!-- Invalid comment template: {error} -->")
