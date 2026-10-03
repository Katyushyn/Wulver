from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError, ProgrammingError
from django.template import Origin, TemplateDoesNotExist
from django.template.loaders.base import Loader as BaseLoader

from .defaults.authentication_templates import AUTHENTICATION_TEMPLATE_NAMES


class Loader(BaseLoader):
    """Load system authentication templates from the database first."""

    def get_template_sources(self, template_name):
        if template_name in AUTHENTICATION_TEMPLATE_NAMES:
            yield Origin(
                name=f"database:{template_name}",
                template_name=template_name,
                loader=self,
            )

    def get_contents(self, origin):
        try:
            from .models import AuthenticationTemplate

            obj = AuthenticationTemplate.objects.filter(
                template_name=origin.template_name
            ).only("code").first()
        except (OperationalError, ProgrammingError, ImproperlyConfigured):
            obj = None

        if obj is None:
            raise TemplateDoesNotExist(origin.template_name)

        return obj.code
