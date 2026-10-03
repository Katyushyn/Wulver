from django.db import migrations, models


def seed_authentication_templates(apps, schema_editor):
    from apps.userprofile.defaults.authentication_templates import (
        AUTHENTICATION_TEMPLATE_CHOICES,
        get_default_authentication_template,
    )

    AuthenticationTemplate = apps.get_model(
        "userprofile", "AuthenticationTemplate"
    )

    for template_name, _label in AUTHENTICATION_TEMPLATE_CHOICES:
        AuthenticationTemplate.objects.update_or_create(
            template_name=template_name,
            defaults={
                "code": get_default_authentication_template(template_name),
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("userprofile", "0003_personal_account_template"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuthenticationTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "template_name",
                    models.CharField(
                        choices=[
                            ("account/_auth_layout.html", "Base authentication layout"),
                            ("account/login.html", "Login"),
                            ("account/signup.html", "Signup"),
                            ("account/email_confirm.html", "Email confirmation"),
                            ("account/verification_sent.html", "Verification sent"),
                            ("account/password_reset.html", "Password reset"),
                            ("account/password_reset_form.html", "Password reset form"),
                            ("account/password_reset_done.html", "Password reset sent"),
                            ("account/password_reset_from_key.html", "Set new password"),
                            ("account/password_reset_from_key_done.html", "Password reset complete"),
                            ("account/email.html", "Email management"),
                            ("account/logout.html", "Logout"),
                            ("account/password_change.html", "Password change"),
                            ("account/password_set.html", "Account password setup"),
                            ("account/reauthenticate.html", "Reauthentication"),
                            ("account/account_inactive.html", "Inactive account"),
                            ("account/verified_email_required.html", "Verified email required"),
                            ("account/signup_closed.html", "Signup closed"),
                            ("socialaccount/login.html", "Social login"),
                            ("socialaccount/signup.html", "Social signup"),
                            ("socialaccount/connections.html", "Social connections"),
                            ("socialaccount/login_cancelled.html", "Social login cancelled"),
                            ("socialaccount/authentication_error.html", "Social authentication error"),
                            ("socialaccount/login_redirect.html", "Social login redirect"),
                        ],
                        max_length=100,
                        unique=True,
                        verbose_name="Authentication template",
                    ),
                ),
                (
                    "code",
                    models.TextField(
                        help_text="Complete Django template code rendered for this account page.",
                        verbose_name="Template code",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Updated at"),
                ),
            ],
            options={
                "verbose_name": "Authentication template",
                "verbose_name_plural": "Authentication templates",
                "ordering": ("template_name",),
            },
        ),
        migrations.RunPython(
            seed_authentication_templates,
            migrations.RunPython.noop,
        ),
        migrations.DeleteModel(
            name="AuthenticationPageText",
        ),
    ]
