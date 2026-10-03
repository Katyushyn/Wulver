AUTHENTICATION_EMAIL_DEFAULTS = {
    "email_confirmation": {
        "en": (
            "Confirm your email address on {{ current_site.name }}",
            """Hello!

You received this email because you registered on {{ current_site.name }} using this email address.

Please follow the link below to confirm your email address and activate your account:

{{ activate_url }}

If you did not create an account, you can safely ignore this email.

Thank you,
{{ current_site.name }}""",
        ),
        "uk": (
            "Підтвердження вашого email на {{ current_site.name }}",
            """Привіт!

Ви отримали цей лист, тому що зареєструвалися на сайті {{ current_site.name }} з цією адресою електронної пошти.

Перейдіть за посиланням нижче, щоб підтвердити адресу email та активувати обліковий запис:

{{ activate_url }}

Якщо ви не створювали обліковий запис, просто проігноруйте цей лист.

Дякуємо,
{{ current_site.name }}""",
        ),
    },
    "email_confirmed": {
        "en": ("Email confirmed", "Your email address on {{ current_site.name }} has been confirmed."),
        "uk": ("Email підтверджено", "Вашу електронну адресу на {{ current_site.name }} підтверджено."),
    },
    "password_reset": {
        "en": (
            "Password reset on {{ current_site.name }}",
            """A password reset was requested for your account.

Use the link below to set a new password:

{{ password_reset_url }}

If you did not request this, you can safely ignore this email.""",
        ),
        "uk": (
            "Відновлення пароля на {{ current_site.name }}",
            """Для вашого облікового запису було запитано відновлення пароля.

Перейдіть за посиланням нижче, щоб встановити новий пароль:

{{ password_reset_url }}

Якщо ви не надсилали цей запит, просто проігноруйте лист.""",
        ),
    },
    "password_reset_complete": {
        "en": ("Password reset complete", "Your password on {{ current_site.name }} has been reset."),
        "uk": ("Пароль відновлено", "Ваш пароль на {{ current_site.name }} було відновлено."),
    },
    "password_changed": {
        "en": ("Password changed", "Your password on {{ current_site.name }} has been changed."),
        "uk": ("Пароль змінено", "Ваш пароль на {{ current_site.name }} було змінено."),
    },
    "password_set": {
        "en": ("Password set", "A password has been set for your account on {{ current_site.name }}."),
        "uk": ("Пароль встановлено", "Для вашого облікового запису на {{ current_site.name }} встановлено пароль."),
    },
    "unknown_account": {
        "en": ("Unknown account", "An attempt was made to access an account using {{ email }}, but no such account exists.\n\nYou can create an account here:\n{{ signup_url }}"),
        "uk": ("Обліковий запис не знайдено", "Була здійснена спроба доступу до облікового запису через {{ email }}, але такого запису не існує.\n\nСтворити обліковий запис можна тут:\n{{ signup_url }}"),
    },
    "account_already_exists": {
        "en": ("Account already exists", "An account using {{ email }} already exists.\n\nIf you forgot the password, reset it here:\n{{ password_reset_url }}"),
        "uk": ("Обліковий запис уже існує", "Обліковий запис з адресою {{ email }} вже існує.\n\nЯкщо ви забули пароль, відновіть його тут:\n{{ password_reset_url }}"),
    },
    "email_changed": {
        "en": ("Email changed", "Your email address was changed from {{ from_email }} to {{ to_email }}."),
        "uk": ("Email змінено", "Вашу електронну адресу змінено з {{ from_email }} на {{ to_email }}."),
    },
    "email_deleted": {
        "en": ("Email removed", "Email address {{ deleted_email }} was removed from your account."),
        "uk": ("Email видалено", "Електронну адресу {{ deleted_email }} видалено з вашого облікового запису."),
    },
}
