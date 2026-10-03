from pathlib import Path


AUTHENTICATION_TEMPLATE_CHOICES = (
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
)

AUTHENTICATION_TEMPLATE_NAMES = frozenset(
    template_name for template_name, _label in AUTHENTICATION_TEMPLATE_CHOICES
)


def get_default_authentication_template(template_name):
    if template_name not in AUTHENTICATION_TEMPLATE_NAMES:
        raise KeyError(template_name)

    templates_root = Path(__file__).resolve().parents[1] / "templates"
    return (templates_root / template_name).read_text(encoding="utf-8")
