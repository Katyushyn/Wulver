import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


def default_backup_directory():
    base_dir = Path(settings.BASE_DIR).resolve()
    return str(base_dir.parent / f"{base_dir.name}_backups")


class BackupSettings(models.Model):
    backup_directory = models.CharField(
        _("Backup directory"),
        max_length=1000,
        default="",
        blank=True,
        help_text=_(
            "Absolute directory outside the public web root. Leave blank to use a private sibling directory next to BASE_DIR."
        ),
    )
    additional_paths = models.TextField(
        _("Additional backup paths"),
        blank=True,
        help_text=_(
            "Optional absolute files or directories outside the Django project, one path per line."
        ),
    )
    compression_level = models.PositiveSmallIntegerField(
        _("ZIP compression level"),
        default=1,
        help_text=_("Use 0 for no compression or a value from 1 to 9. Level 1 minimizes server load."),
    )
    maximum_upload_size_mb = models.PositiveIntegerField(
        _("Maximum uploaded backup size (MB)"),
        default=10240,
        help_text=_("Maximum size accepted when a backup ZIP is uploaded from a computer."),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Backup settings")
        verbose_name_plural = _("Backup settings")

    def __str__(self):
        return str(_("Backup settings"))

    def clean(self):
        super().clean()
        if not 0 <= self.compression_level <= 9:
            raise ValidationError({"compression_level": _("Enter a value from 0 to 9.")})
        path = Path(self.backup_directory).expanduser() if self.backup_directory else None
        if path and not path.is_absolute():
            raise ValidationError({"backup_directory": _("Enter an absolute filesystem path.")})
        invalid_additional = [
            value.strip()
            for value in self.additional_paths.splitlines()
            if value.strip() and not Path(value.strip()).expanduser().is_absolute()
        ]
        if invalid_additional:
            raise ValidationError(
                {
                    "additional_paths": _("Every additional backup path must be absolute: %(paths)s")
                    % {"paths": ", ".join(invalid_additional)}
                }
            )

    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def get_additional_paths(self):
        return tuple(
            Path(value.strip()).expanduser().resolve()
            for value in self.additional_paths.splitlines()
            if value.strip()
        )

    @property
    def resolved_backup_directory(self):
        value = self.backup_directory or default_backup_directory()
        return Path(value).expanduser().resolve()


class BackupSnapshot(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Creating")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        RESTORING = "restoring", _("Restoring")

    class Source(models.TextChoices):
        CREATED = "created", _("Created on this server")
        UPLOADED = "uploaded", _("Uploaded from a computer")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.CharField(_("Description"), max_length=255, blank=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    source = models.CharField(
        _("Source"),
        max_length=20,
        choices=Source.choices,
        default=Source.CREATED,
    )
    archive_path = models.CharField(_("Archive path"), max_length=2000, blank=True)
    storage_root = models.CharField(_("Storage root"), max_length=1000, blank=True)
    archive_name = models.CharField(_("Archive name"), max_length=255, blank=True)
    archive_size = models.PositiveBigIntegerField(_("Archive size"), default=0)
    sha256 = models.CharField(_("SHA-256"), max_length=64, blank=True)
    database_vendor = models.CharField(_("Database vendor"), max_length=50, blank=True)
    manifest = models.JSONField(_("Manifest"), default=dict, blank=True)
    error_message = models.TextField(_("Error message"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Created by"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backup_snapshots",
    )
    started_at = models.DateTimeField(_("Started at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("Completed at"), null=True, blank=True)
    verified_at = models.DateTimeField(_("Verified at"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Backup")
        verbose_name_plural = _("Backups")
        ordering = ("-created_at",)

    def __str__(self):
        return self.archive_name or f"Backup {self.created_at:%Y-%m-%d %H:%M:%S}"

    @property
    def archive_file(self):
        return Path(self.archive_path).expanduser().resolve() if self.archive_path else None

    @property
    def archive_exists(self):
        path = self.archive_file
        return bool(path and path.is_file())

    def _delete_archive(self):
        path = self.archive_file
        if not path or not path.exists():
            return
        root = (
            Path(self.storage_root).expanduser().resolve()
            if self.storage_root
            else BackupSettings.get_solo().resolved_backup_directory
        )
        try:
            path.relative_to(root)
        except ValueError as error:
            raise SuspiciousFileOperation(
                _("Refusing to delete a backup outside the configured backup directory.")
            ) from error
        path.unlink()

    def delete(self, *args, **kwargs):
        self._delete_archive()
        return super().delete(*args, **kwargs)
