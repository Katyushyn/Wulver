from django import forms
from django.utils.translation import gettext_lazy as _


class ThemeZipUploadForm(forms.Form):
    zip_file = forms.FileField(
        label=_("ZIP archive"),
        help_text=_("Archive must contain one root folder with theme files."),
        widget=forms.ClearableFileInput(
            attrs={
                "class": (
                    "my-2 block w-full cursor-pointer rounded-default border "
                    "border-base-300 bg-white px-3 py-2 text-sm shadow-xs "
                    "dark:border-base-700 dark:bg-base-900"
                ),
            }
        ),
    )
