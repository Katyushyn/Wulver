import ssl

import certifi
from django.core.mail.backends.smtp import EmailBackend
from django.utils.functional import cached_property


class CertifiEmailBackend(EmailBackend):
    """SMTP backend using certifi's CA bundle for TLS verification."""

    @cached_property
    def ssl_context(self):
        if self.ssl_certfile or self.ssl_keyfile:
            return super().ssl_context

        return ssl.create_default_context(cafile=certifi.where())
