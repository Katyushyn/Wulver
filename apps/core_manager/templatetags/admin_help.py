from django import template

from apps.core_manager.admin_help import get_admin_help


register = template.Library()


@register.inclusion_tag("admin/help/button.html")
def admin_help_button(opts, placement="list"):
    return {
        "admin_help": get_admin_help(opts),
        "placement": placement,
    }


@register.inclusion_tag("admin/help/dialog.html")
def admin_help_dialog(opts):
    return {"admin_help": get_admin_help(opts)}
