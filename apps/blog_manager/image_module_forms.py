from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .image_module_storage import validate_image_uploads
from .models import ImageModule


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_clean = super().clean
        if not data:
            return []
        return [single_clean(item, initial) for item in data]


class ImageModuleAdminForm(forms.ModelForm):
    uploads = MultipleImageField(
        required=False,
        label=_("Upload images"),
        help_text=(
            _(
                "Select up to 100 JPEG, PNG, WebP or AVIF files. "
                "Maximum 25 MB per file and 500 MB per module."
            )
        ),
    )
    manifest_editor = forms.JSONField(
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = ImageModule
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manifest_editor"].initial = list(self.instance.manifest or [])

    def clean_manifest_editor(self):
        submitted = self.cleaned_data.get("manifest_editor") or []
        if not isinstance(submitted, list):
            raise ValidationError(_("Invalid image manifest."))

        existing = {
            str(item.get("id")): item
            for item in (self.instance.manifest or [])
            if item.get("id")
        }
        cleaned = []
        seen = set()
        for submitted_item in submitted:
            if not isinstance(submitted_item, dict):
                continue
            item_id = str(submitted_item.get("id") or "")
            if item_id not in existing or item_id in seen:
                continue
            item = dict(existing[item_id])
            item["alt"] = str(submitted_item.get("alt") or "").strip()[:250]
            item["active"] = submitted_item.get("active") is not False
            cleaned.append(item)
            seen.add(item_id)
        return cleaned

    def clean(self):
        cleaned_data = super().clean()
        manifest = cleaned_data.get("manifest_editor") or []
        uploads = cleaned_data.get("uploads") or []
        validate_image_uploads(uploads, manifest)
        return cleaned_data
