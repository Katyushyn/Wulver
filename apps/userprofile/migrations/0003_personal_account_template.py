from django.db import migrations, models


def create_personal_account_template(apps, schema_editor):
    from apps.userprofile.defaults.personal_account import (
        DEFAULT_PERSONAL_ACCOUNT_TEMPLATE,
    )

    AuthenticationSettings = apps.get_model(
        "userprofile", "AuthenticationSettings"
    )
    PersonalAccountTemplate = apps.get_model(
        "userprofile", "PersonalAccountTemplate"
    )
    Page = apps.get_model("core_manager", "Page")
    ThemeTemplate = apps.get_model("theme_manager", "ThemeTemplate")

    PersonalAccountTemplate.objects.update_or_create(
        pk=1,
        defaults={"code": DEFAULT_PERSONAL_ACCOUNT_TEMPLATE},
    )

    old_page_ids = list(
        AuthenticationSettings.objects.exclude(
            personal_information_page_id=None
        ).values_list("personal_information_page_id", flat=True)
    )
    AuthenticationSettings.objects.update(personal_information_page_id=None)

    old_pages = Page.objects.filter(
        pk__in=old_page_ids,
        slug="personal-account",
        template__slug="personal-account",
    )
    old_template_ids = list(old_pages.values_list("template_id", flat=True))
    old_pages.delete()
    ThemeTemplate.objects.filter(
        pk__in=old_template_ids,
        slug="personal-account",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("userprofile", "0002_seed_defaults"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonalAccountTemplate",
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
                    "code",
                    models.TextField(
                        help_text="Django template code used for the authenticated user's personal account page.",
                        verbose_name="Template code",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Updated at"),
                ),
            ],
            options={
                "verbose_name": "Personal account template",
                "verbose_name_plural": "Personal account template",
            },
        ),
        migrations.RunPython(
            create_personal_account_template,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="authenticationsettings",
            name="personal_information_page",
        ),
    ]
