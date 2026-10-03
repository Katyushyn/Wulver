from django import template

from apps.blog_manager.models import Category

register = template.Library()


@register.simple_tag
def get_blog_category_children(parent_id):
    return Category.objects.filter(parent_id=parent_id).order_by(
        "sort_order",
        "title",
        "id",
    )
