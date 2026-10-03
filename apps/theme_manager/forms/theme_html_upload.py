from django import forms
from django.utils.translation import gettext_lazy as _


class ThemeZipUploadForm(forms.Form):
    zip_file = forms.FileField(
        label=_("ZIP archive"),
        help_text=_("Archive must contain one root folder with theme files."),
    )