from django.apps import AppConfig


class UserprofileConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.userprofile"

    def ready(self):
        from django.contrib.auth.models import User

        def avatar_url(user):
            if hasattr(user, "userprofile") and user.userprofile.avatar:
                try:
                    return user.userprofile.avatar.url
                except ValueError:
                    return None
            return None

        User.add_to_class("avatar_url", property(avatar_url))
