import random
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .mixins import AvatarProcessingMixin


DEFAULT_AUTH_STYLESHEET = """/* Styles shared by all authentication pages. */
.auth-page {
    background: #f3f4f6;
    color: #1f2937;
}

.auth-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    box-shadow: 0 20px 45px rgba(15, 23, 42, 0.12);
}

.auth-logo {
    display: block;
    max-height: 72px;
    max-width: 220px;
    margin: 0 auto 24px;
}

.auth-page a { color: #2563eb; }
.auth-page .form-control { border-color: #d1d5db; border-radius: 10px; }
.auth-page .btn-primary { background: #2563eb; border-color: #2563eb; color: #ffffff; }
"""


class AuthenticationSettings(models.Model):
    logo = models.ImageField(
        _("Authentication logo"),
        upload_to="userprofile/authentication/",
        blank=True,
        null=True,
        help_text=_("Falls back to the organization logo from Site settings."),
    )
    stylesheet = models.TextField(
        _("Authentication stylesheet"),
        default=DEFAULT_AUTH_STYLESHEET,
        help_text=_("CSS applied to all system authentication pages."),
    )
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Authentication appearance")
        verbose_name_plural = _("Authentication appearance")

    def __str__(self):
        return str(_("Authentication appearance"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class PersonalAccountTemplate(models.Model):
    code = models.TextField(
        _("Template code"),
        help_text=_(
            "Django template code used for the authenticated user's personal account page."
        ),
    )
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Personal account template")
        verbose_name_plural = _("Personal account template")

    def __str__(self):
        return str(_("Personal account template"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def get_solo(cls):
        from .defaults.personal_account import DEFAULT_PERSONAL_ACCOUNT_TEMPLATE

        obj, _created = cls.objects.get_or_create(
            pk=1,
            defaults={"code": DEFAULT_PERSONAL_ACCOUNT_TEMPLATE},
        )
        return obj


class AuthenticationTemplate(models.Model):
    from .defaults.authentication_templates import AUTHENTICATION_TEMPLATE_CHOICES

    template_name = models.CharField(
        _("Authentication template"),
        max_length=100,
        choices=AUTHENTICATION_TEMPLATE_CHOICES,
        unique=True,
    )
    code = models.TextField(
        _("Template code"),
        help_text=_("Complete Django template code rendered for this account page."),
    )
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Authentication template")
        verbose_name_plural = _("Authentication templates")
        ordering = ("template_name",)

    def __str__(self):
        return self.get_template_name_display()


class AuthenticationEmailTemplate(models.Model):
    class EmailType(models.TextChoices):
        EMAIL_CONFIRMATION = "email_confirmation", _("Email confirmation")
        EMAIL_CONFIRMED = "email_confirmed", _("Email confirmed")
        PASSWORD_RESET = "password_reset", _("Password reset")
        PASSWORD_RESET_COMPLETE = "password_reset_complete", _("Password reset complete")
        PASSWORD_CHANGED = "password_changed", _("Password changed")
        PASSWORD_SET = "password_set", _("Password set")
        UNKNOWN_ACCOUNT = "unknown_account", _("Unknown account")
        ACCOUNT_ALREADY_EXISTS = "account_already_exists", _("Account already exists")
        EMAIL_CHANGED = "email_changed", _("Email changed")
        EMAIL_DELETED = "email_deleted", _("Email removed")

    email_type = models.CharField(
        _("Authentication email"),
        max_length=40,
        choices=EmailType.choices,
        unique=True,
    )
    subject = models.CharField(_("Subject"), max_length=255)
    message = models.TextField(
        _("Message template"),
        help_text=_(
            "Django template variables are supported, for example {{ activate_url }}."
        ),
    )
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Authentication email template")
        verbose_name_plural = _("Authentication email templates")
        ordering = ("email_type",)

    def __str__(self):
        return self.get_email_type_display()


class UserProfile(models.Model, AvatarProcessingMixin):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="userprofile",
        verbose_name=_("User"),
    )
    avatar = models.ImageField(
        _("Avatar"), upload_to="avatars/", blank=True, null=True
    )
    prompt = models.TextField(blank=True, verbose_name=_("Prompt"))

    share_token = models.CharField(
        _("Share token"), max_length=6, blank=True, null=True
    )
    share_token_created = models.DateTimeField(
        _("Share token created"), blank=True, null=True
    )

    def __str__(self):
        return f"Profile of {self.user.username}"

    class Meta:
        verbose_name = _("Additional option")
        verbose_name_plural = _("Additional options")
        ordering = ["id"]

    def save(self, *args, **kwargs):
        previous_avatar_name = ""
        if self.pk:
            previous_avatar_name = (
                self.__class__.objects
                .filter(pk=self.pk)
                .values_list("avatar", flat=True)
                .first()
                or ""
            )

        super().save(*args, **kwargs)
        current_avatar_name = self.avatar.name if self.avatar else ""
        if previous_avatar_name and not current_avatar_name:
            avatar_storage = self._meta.get_field("avatar").storage
            if avatar_storage.exists(previous_avatar_name):
                avatar_storage.delete(previous_avatar_name)
            return

        if current_avatar_name and current_avatar_name != previous_avatar_name:
            if self.process_avatar(previous_name=previous_avatar_name):
                self.__class__.objects.filter(pk=self.pk).update(
                    avatar=self.avatar.name
                )

    def generate_share_token(self):
        self.share_token = f"{random.randint(0, 999999):06d}"
        self.share_token_created = timezone.now()
        self.save(update_fields=["share_token", "share_token_created"])
        return self.share_token

    def is_share_token_valid(self):
        if not self.share_token or not self.share_token_created:
            return False
        return (
            timezone.now() - self.share_token_created
            <= timezone.timedelta(minutes=10)
        )

# ==========================================
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        if hasattr(instance, "userprofile"):
            instance.userprofile.save()
