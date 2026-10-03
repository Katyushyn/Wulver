from django import forms
from django.utils.translation import gettext_lazy as _
from unfold.widgets import (
    UnfoldAdminFileFieldWidget,
    UnfoldAdminPasswordWidget,
    UnfoldAdminSelectWidget,
    UnfoldAdminTextInputWidget,
    UnfoldBooleanSwitchWidget,
)

from apps.backup_manager.models import BackupSnapshot


class CreateBackupForm(forms.Form):
    description = forms.CharField(
        label=_("Description"),
        max_length=255,
        required=False,
        widget=UnfoldAdminTextInputWidget(),
        help_text=_("Optional note, for example: Before updating the active theme."),
    )
    password = forms.CharField(
        label=_("Backup password"),
        widget=UnfoldAdminPasswordWidget(attrs={"autocomplete": "new-password"}),
        help_text=_("Required every time. The password is never saved by Wulver."),
        min_length=8,
    )
    password_confirm = forms.CharField(
        label=_("Confirm password"),
        widget=UnfoldAdminPasswordWidget(attrs={"autocomplete": "new-password"}),
        min_length=8,
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password") != cleaned.get("password_confirm"):
            self.add_error("password_confirm", _("The passwords do not match."))
        return cleaned


class RestoreBackupForm(forms.Form):
    snapshot = forms.ModelChoiceField(
        label=_("Saved backup"),
        queryset=BackupSnapshot.objects.none(),
        required=False,
        widget=UnfoldAdminSelectWidget(),
    )
    uploaded_backup = forms.FileField(
        label=_("Or upload a backup ZIP"),
        required=False,
        widget=UnfoldAdminFileFieldWidget(
            attrs={"accept": ".zip,application/zip"},
        ),
        help_text=_("Select an encrypted Wulver backup previously downloaded to your computer."),
    )
    description = forms.CharField(
        label=_("Uploaded backup description"),
        max_length=255,
        required=False,
        widget=UnfoldAdminTextInputWidget(),
    )
    password = forms.CharField(
        label=_("Backup password"),
        widget=UnfoldAdminPasswordWidget(attrs={"autocomplete": "current-password"}),
        min_length=8,
    )
    confirmation = forms.BooleanField(
        label=_("I understand that the current site files and database will be replaced."),
        widget=UnfoldBooleanSwitchWidget(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["snapshot"].queryset = BackupSnapshot.objects.filter(
            status=BackupSnapshot.Status.COMPLETED
        ).order_by("-created_at")

    def clean(self):
        cleaned = super().clean()
        selected = bool(cleaned.get("snapshot"))
        uploaded = bool(cleaned.get("uploaded_backup"))
        if selected == uploaded:
            raise forms.ValidationError(
                _("Choose one saved backup or upload one backup ZIP, but not both.")
            )
        return cleaned


class VerifyBackupForm(forms.Form):
    password = forms.CharField(
        label=_("Backup password"),
        widget=UnfoldAdminPasswordWidget(attrs={"autocomplete": "current-password"}),
        min_length=8,
    )
