from django import forms

from .image_processing import (
    APPLE_TOUCH_ICON_SPEC,
    FAVICON_ICO_SPEC,
    FAVICON_PNG_SPEC,
    ORGANIZATION_LOGO_SPEC,
    PERSON_IMAGE_SPEC,
    SOCIAL_PREVIEW_SPEC,
    process_uploaded_image,
)
from .models import Page, SiteSettings


class ImageProcessingModelForm(forms.ModelForm):
    image_specs = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, spec in self.image_specs.items():
            self.fields[field_name].help_text = spec.help_text

    def clean(self):
        cleaned_data = super().clean()

        for field_name, spec in self.image_specs.items():
            if field_name not in self.changed_data:
                continue

            uploaded_file = cleaned_data.get(field_name)
            if not uploaded_file:
                continue

            try:
                cleaned_data[field_name] = process_uploaded_image(
                    uploaded_file,
                    spec,
                )
            except forms.ValidationError as error:
                self.add_error(field_name, error)

        return cleaned_data


class SiteSettingsAdminForm(ImageProcessingModelForm):
    image_specs = {
        "default_preview_image": SOCIAL_PREVIEW_SPEC,
        "favicon_ico": FAVICON_ICO_SPEC,
        "favicon_png": FAVICON_PNG_SPEC,
        "apple_touch_icon": APPLE_TOUCH_ICON_SPEC,
        "organization_logo": ORGANIZATION_LOGO_SPEC,
        "person_image": PERSON_IMAGE_SPEC,
    }

    class Meta:
        model = SiteSettings
        fields = "__all__"


class PageAdminForm(ImageProcessingModelForm):
    image_specs = {
        "preview_image": SOCIAL_PREVIEW_SPEC,
    }

    class Meta:
        model = Page
        fields = "__all__"
