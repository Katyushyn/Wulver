class SingletonAdminMixin:
    """Admin behavior shared by settings models with one effective record."""

    def render_change_form(
        self,
        request,
        context,
        add=False,
        change=False,
        form_url="",
        obj=None,
    ):
        context = dict(context)
        context["show_save_and_continue"] = False
        return super().render_change_form(
            request,
            context,
            add=add,
            change=change,
            form_url=form_url,
            obj=obj,
        )
