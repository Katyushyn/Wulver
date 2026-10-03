import io
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pillow_avif  # noqa: F401
from PIL import Image
from django.contrib.auth.models import User
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.template.loader import get_template
from django.template.loader import render_to_string
from django.utils import translation
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from apps.theme_manager.models import Theme
from allauth.account.models import EmailAddress
from .models import (
    AuthenticationEmailTemplate,
    AuthenticationSettings,
    AuthenticationTemplate,
    PersonalAccountTemplate,
)
from .templatetags.authentication_controls import authentication_button_url
from .defaults.authentication_emails import AUTHENTICATION_EMAIL_DEFAULTS
from .defaults.personal_account import DEFAULT_PERSONAL_ACCOUNT_TEMPLATE
from .defaults.authentication_templates import (
    AUTHENTICATION_TEMPLATE_CHOICES,
    get_default_authentication_template,
)
from .email_backend import CertifiEmailBackend


class AuthenticationCustomizationTest(TestCase):
    def test_certifi_email_backend_has_verified_ca_store(self):
        context = CertifiEmailBackend().ssl_context

        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_login_with_unverified_email_routes_to_confirmation_without_error(self):
        user = User.objects.create_user(
            username="login-user",
            email="login-user@example.com",
            password="test-password",
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=False,
        )

        response = self.client.post(
            f"{reverse('account_login')}?next=%2F",
            {
                "login": user.email,
                "password": "test-password",
                "remember": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("account_email_verification_sent"),
            fetch_redirect_response=False,
        )

    def test_login_template_displays_invalid_credentials_error(self):
        response = self.client.post(
            reverse("account_login"),
            {
                "login": "missing-user@example.com",
                "password": "incorrect-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertContains(response, 'class="alert alert-danger"')

    def test_login_with_verified_email_redirects_to_requested_page(self):
        user = User.objects.create_user(
            username="verified-login-user",
            email="verified-login-user@example.com",
            password="test-password",
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )

        response = self.client.post(
            f"{reverse('account_login')}?next=%2F",
            {
                "login": user.email,
                "password": "test-password",
                "remember": "on",
            },
        )

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

    def test_login_accepts_username(self):
        user = User.objects.create_user(
            username="username-login-user",
            email="username-login-user@example.com",
            password="test-password",
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )

        response = self.client.post(
            reverse("account_login"),
            {
                "login": user.username,
                "password": "test-password",
                "remember": "on",
            },
        )

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

    def test_authentication_email_templates_are_seeded_and_render_variables(self):
        self.assertEqual(
            AuthenticationEmailTemplate.objects.count(),
            len(AuthenticationEmailTemplate.EmailType.choices),
        )

        with translation.override("uk"):
            subject = render_to_string(
                "account/email/email_confirmation_subject.txt",
                {"current_site": SimpleNamespace(name="Wulver")},
            ).strip()
            message = render_to_string(
                "account/email/email_confirmation_message.txt",
                {
                    "current_site": SimpleNamespace(name="Wulver"),
                    "activate_url": "https://example.com/confirm/?key=abc&next=/",
                },
            )

        self.assertIn("Wulver", subject)
        self.assertIn("Підтвердження", subject)
        self.assertIn("https://example.com/confirm/?key=abc&next=/", message)
        self.assertNotIn("{{ activate_url }}", message)

    def test_admin_can_reset_one_authentication_email_to_defaults(self):
        admin_user = User.objects.create_superuser(
            username="email-admin",
            email="admin@example.com",
            password="password",
        )
        email_template = AuthenticationEmailTemplate.objects.get(
            email_type=AuthenticationEmailTemplate.EmailType.EMAIL_CONFIRMATION
        )
        email_template.subject_en = "Broken subject"
        email_template.subject_uk = "Зламана тема"
        email_template.message_en = "Broken message"
        email_template.message_uk = "Зламаний текст"
        email_template.save()
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse(
                "admin:userprofile_authenticationemailtemplate_reset_defaults",
                args=[email_template.pk],
            )
        )

        self.assertEqual(response.status_code, 302)
        email_template.refresh_from_db()
        defaults = AUTHENTICATION_EMAIL_DEFAULTS["email_confirmation"]
        self.assertEqual(email_template.subject_en, defaults["en"][0])
        self.assertEqual(email_template.message_en, defaults["en"][1])
        self.assertEqual(email_template.subject_uk, defaults["uk"][0])
        self.assertEqual(email_template.message_uk, defaults["uk"][1])

    def test_authentication_templates_are_seeded_and_compile(self):
        self.assertEqual(
            AuthenticationTemplate.objects.count(),
            len(AUTHENTICATION_TEMPLATE_CHOICES),
        )

        for template_name, _label in AUTHENTICATION_TEMPLATE_CHOICES:
            with self.subTest(template=template_name):
                self.assertIsNotNone(get_template(template_name))
                self.assertTrue(
                    AuthenticationTemplate.objects.filter(
                        template_name=template_name
                    ).exists()
                )

    def test_logout_uses_custom_system_template(self):
        user = User.objects.create_user(username="logout-user", password="password")
        self.client.force_login(user)

        response = self.client.get(reverse("account_logout"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/logout.html")
        self.assertTemplateUsed(response, "account/_auth_layout.html")

    def test_authentication_button_sends_guest_to_login_and_back(self):
        request = RequestFactory().get("/articles/example/?page=2")
        request.user = AnonymousUser()

        url = authentication_button_url({"request": request})

        self.assertEqual(
            url,
            f"{reverse('account_login')}?next=%2Farticles%2Fexample%2F%3Fpage%3D2",
        )

    def test_authentication_button_uses_system_personal_account_page(self):
        request = RequestFactory().get("/")
        request.user = User.objects.create_user(username="member")

        self.assertEqual(
            authentication_button_url({"request": request}),
            reverse("personal_account"),
        )

    def test_system_personal_account_page_requires_authentication(self):
        Theme.objects.create(name="Sample theme", slug="sample-theme", is_active=True)
        account_url = reverse("personal_account")

        response = self.client.get(account_url)

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={account_url}",
            fetch_redirect_response=False,
        )

        user = User.objects.create_user(
            username="account-owner",
            email="owner@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(account_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your account")
        self.assertContains(response, 'content="noindex, nofollow"')
        self.assertContains(response, reverse("account_email"))
        self.assertContains(response, reverse("account_change_password"))
        self.assertContains(response, reverse("socialaccount_connections"))
        self.assertContains(response, "auth-card--account")

    def test_admin_can_reset_personal_account_template_to_default(self):
        admin_user = User.objects.create_superuser(
            username="account-template-admin",
            email="admin@example.com",
            password="password",
        )
        account_template = PersonalAccountTemplate.get_solo()
        account_template.code = "custom template"
        account_template.save()
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse(
                "admin:userprofile_personalaccounttemplate_reset_defaults",
                args=[account_template.pk],
            )
        )

        self.assertEqual(response.status_code, 302)
        account_template.refresh_from_db()
        self.assertEqual(account_template.code, DEFAULT_PERSONAL_ACCOUNT_TEMPLATE)

    def test_personal_account_admin_combines_appearance_and_template(self):
        admin_user = User.objects.create_superuser(
            username="combined-account-admin",
            email="admin@example.com",
            password="password",
        )
        account_template = PersonalAccountTemplate.get_solo()
        settings = AuthenticationSettings.get_solo()
        self.client.force_login(admin_user)
        combined_url = reverse(
            "admin:userprofile_personalaccounttemplate_change",
            args=[account_template.pk],
        )

        response = self.client.get(combined_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="logo"')
        self.assertContains(response, 'name="stylesheet"')
        self.assertContains(response, 'name="code"')

        response = self.client.post(
            combined_url,
            {
                "stylesheet": ".auth-page { color: navy; }",
                "code": "{% extends base_template %}{% block main %}Account{% endblock %}",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        settings.refresh_from_db()
        account_template.refresh_from_db()
        self.assertEqual(settings.stylesheet, ".auth-page { color: navy; }")
        self.assertIn("Account", account_template.code)

        legacy_url = reverse(
            "admin:userprofile_authenticationsettings_change",
            args=[settings.pk],
        )
        response = self.client.get(legacy_url)
        self.assertRedirects(response, combined_url, fetch_redirect_response=False)

    def test_email_management_uses_editable_database_template(self):
        user = User.objects.create_user(
            username="email-owner",
            email="owner@example.com",
            password="test-password",
        )
        auth_template = AuthenticationTemplate.objects.get(
            template_name="account/email.html"
        )
        auth_template.code = auth_template.code.replace(
            '{% trans "Email addresses" %}',
            "Manage your addresses",
        ).replace(
            '{% trans "Add email" %}',
            "Add another address",
        )
        auth_template.save()
        self.client.force_login(user)

        response = self.client.get(
            reverse("account_email"),
            HTTP_ACCEPT_LANGUAGE="en",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/email.html")
        self.assertTemplateUsed(response, "account/_auth_layout.html")
        self.assertContains(response, "Manage your addresses")
        self.assertContains(response, "Add another address")
        self.assertContains(response, 'name="action_add"')

    def test_stylesheet_endpoint_returns_saved_css(self):
        settings = AuthenticationSettings.get_solo()
        settings.stylesheet = ".auth-card { color: rebeccapurple; }"
        settings.save()

        response = self.client.get(reverse("authentication_stylesheet"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/css; charset=utf-8")
        self.assertContains(response, "rebeccapurple")

    def test_login_uses_editable_database_template(self):
        auth_template = AuthenticationTemplate.objects.get(
            template_name="account/login.html"
        )
        auth_template.code = auth_template.code.replace(
            "{% trans 'Website sign in' %}",
            "Welcome back",
        ).replace(
            "{% trans 'Sign in' %}",
            "Continue securely",
        )
        auth_template.save()

        response = self.client.get(reverse("account_login"), HTTP_ACCEPT_LANGUAGE="en")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back")
        self.assertContains(response, "Continue securely")
        self.assertContains(response, reverse("authentication_stylesheet"))
        self.assertTemplateUsed(response, "account/_auth_layout.html")

    def test_admin_can_reset_authentication_template_to_default(self):
        admin_user = User.objects.create_superuser(
            username="auth-template-admin",
            email="auth-template-admin@example.com",
            password="password",
        )
        auth_template = AuthenticationTemplate.objects.get(
            template_name="account/login.html"
        )
        auth_template.code = "custom"
        auth_template.save()
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse(
                "admin:userprofile_authenticationtemplate_reset_defaults",
                args=[auth_template.pk],
            )
        )

        self.assertEqual(response.status_code, 302)
        auth_template.refresh_from_db()
        self.assertEqual(
            auth_template.code,
            get_default_authentication_template("account/login.html"),
        )

    def test_authentication_settings_is_singleton(self):
        first = AuthenticationSettings.get_solo()
        second = AuthenticationSettings(stylesheet=".auth-page {}")
        second.save()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(AuthenticationSettings.objects.count(), 1)


def make_image(size=(300, 200), image_format="JPEG"):
    output = io.BytesIO()
    Image.new("RGB", size, "blue").save(output, format=image_format)
    return output.getvalue()


class AvatarStorageTest(TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.media_root = Path(self.temp_directory.name)
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def test_uploaded_avatar_is_saved_as_square_avif_in_media(self):
        user = User.objects.create_user(username="avatar-user")
        profile = user.userprofile
        profile.avatar = SimpleUploadedFile(
            "portrait.jpg",
            make_image((240, 400)),
            content_type="image/jpeg",
        )

        profile.save()
        profile.refresh_from_db()

        self.assertTrue(profile.avatar.name.startswith("avatars/"))
        self.assertTrue(profile.avatar.name.endswith(".avif"))
        self.assertTrue(Path(profile.avatar.path).is_file())
        self.assertFalse((self.media_root / "avatars" / "portrait.jpg").exists())
        with Image.open(profile.avatar.path) as avatar:
            self.assertEqual(avatar.format, "AVIF")
            self.assertEqual(avatar.size, (150, 150))

    def test_unchanged_avatar_is_not_processed_again(self):
        user = User.objects.create_user(username="stable-avatar-user")
        profile = user.userprofile
        profile.avatar = SimpleUploadedFile(
            "avatar.jpg",
            make_image(),
            content_type="image/jpeg",
        )
        profile.save()
        profile.refresh_from_db()
        avatar_name = profile.avatar.name

        profile.prompt = "Updated prompt"
        profile.save()
        profile.refresh_from_db()

        self.assertEqual(profile.avatar.name, avatar_name)

    def test_replacing_avatar_removes_previous_file(self):
        user = User.objects.create_user(username="replacement-avatar-user")
        profile = user.userprofile
        profile.avatar = SimpleUploadedFile(
            "first.jpg",
            make_image(),
            content_type="image/jpeg",
        )
        profile.save()
        profile.refresh_from_db()
        old_path = Path(profile.avatar.path)

        profile.avatar = SimpleUploadedFile(
            "second.png",
            make_image((400, 240), "PNG"),
            content_type="image/png",
        )
        profile.save()
        profile.refresh_from_db()

        self.assertFalse(old_path.exists())
        self.assertTrue(Path(profile.avatar.path).exists())
        self.assertTrue(profile.avatar.name.endswith(".avif"))

    def test_clearing_avatar_removes_previous_file(self):
        user = User.objects.create_user(username="clear-avatar-user")
        profile = user.userprofile
        profile.avatar = SimpleUploadedFile(
            "avatar.jpg",
            make_image(),
            content_type="image/jpeg",
        )
        profile.save()
        profile.refresh_from_db()
        old_path = Path(profile.avatar.path)

        profile.avatar = None
        profile.save()
        profile.refresh_from_db()

        self.assertFalse(profile.avatar)
        self.assertFalse(old_path.exists())
