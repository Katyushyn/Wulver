from datetime import timedelta
from pathlib import Path

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.core_manager.admin_mixins import SingletonAdminMixin
from apps.backup_manager.forms import CreateBackupForm, RestoreBackupForm, VerifyBackupForm
from apps.backup_manager.models import BackupSettings, BackupSnapshot
from apps.backup_manager.services import (
    BackupArchiveError,
    import_backup_archive,
    verify_backup_archive,
)
from apps.backup_manager.services.jobs import BackupJobError, spawn_backup_job


def _human_size(value):
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024


class SuperuserBackupAdminMixin:
    def _require_superuser(self, request):
        if not request.user.is_active or not request.user.is_superuser:
            raise PermissionDenied

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_superuser)


@admin.register(BackupSettings)
class BackupSettingsAdmin(SingletonAdminMixin, SuperuserBackupAdminMixin, ModelAdmin):
    readonly_fields = ("effective_backup_directory", "created_at", "updated_at")
    fieldsets = (
        (
            _("Storage"),
            {
                "fields": (
                    "backup_directory",
                    "effective_backup_directory",
                    "additional_paths",
                    "maximum_upload_size_mb",
                )
            },
        ),
        (
            _("Archive"),
            {"fields": ("compression_level",)},
        ),
        (
            _("System"),
            {"classes": ("collapse",), "fields": ("created_at", "updated_at")},
        ),
    )

    def has_add_permission(self, request):
        return bool(request.user.is_superuser and not BackupSettings.objects.exists())

    def effective_backup_directory(self, obj):
        return str(obj.resolved_backup_directory) if obj else "—"

    effective_backup_directory.short_description = _("Effective backup directory")

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        self._require_superuser(request)
        obj = BackupSettings.get_solo()
        return redirect("admin:backup_manager_backupsettings_change", obj.pk)


@admin.register(BackupSnapshot)
class BackupSnapshotAdmin(SuperuserBackupAdminMixin, ModelAdmin):
    change_list_template = "admin/backup_manager/backupsnapshot/change_list.html"
    list_display = (
        "archive_name_display",
        "status",
        "source",
        "database_vendor",
        "archive_size_display",
        "created_by",
        "created_at",
        "actions_display",
    )
    list_filter = ("status", "source", "database_vendor", "created_at")
    search_fields = ("archive_name", "description", "sha256", "error_message")
    readonly_fields = (
        "id",
        "description",
        "status",
        "source",
        "archive_path",
        "storage_root",
        "archive_name",
        "archive_size_display",
        "sha256",
        "database_vendor",
        "manifest",
        "error_message",
        "created_by",
        "started_at",
        "completed_at",
        "verified_at",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields

    def get_actions(self, request):
        return {}

    def archive_name_display(self, obj):
        return obj.archive_name or obj.description or str(obj.pk)

    archive_name_display.short_description = _("Backup")

    def archive_size_display(self, obj):
        return _human_size(obj.archive_size)

    archive_size_display.short_description = _("Size")

    def actions_display(self, obj):
        if obj.status != BackupSnapshot.Status.COMPLETED or not obj.archive_exists:
            return "—"
        return format_html(
            '<a class="button" href="{}">{}</a>&nbsp;'
            '<a class="button" href="{}">{}</a>&nbsp;'
            '<a class="button" href="{}?snapshot={}">{}</a>',
            reverse("admin:backup_manager_backupsnapshot_download", args=[obj.pk]),
            _("Download"),
            reverse("admin:backup_manager_backupsnapshot_verify", args=[obj.pk]),
            _("Verify"),
            reverse("admin:backup_manager_backupsnapshot_restore"),
            obj.pk,
            _("Restore"),
        )

    actions_display.short_description = _("Actions")

    def get_urls(self):
        return [
            path(
                "create-full/",
                self.admin_site.admin_view(self.create_backup_view),
                name="backup_manager_backupsnapshot_create_full",
            ),
            path(
                "restore/",
                self.admin_site.admin_view(self.restore_backup_view),
                name="backup_manager_backupsnapshot_restore",
            ),
            path(
                "<uuid:object_id>/download/",
                self.admin_site.admin_view(self.download_backup_view),
                name="backup_manager_backupsnapshot_download",
            ),
            path(
                "<uuid:object_id>/verify/",
                self.admin_site.admin_view(self.verify_backup_view),
                name="backup_manager_backupsnapshot_verify",
            ),
        ] + super().get_urls()

    def _active_job_exists(self):
        active = BackupSnapshot.objects.filter(
            status__in=(
                BackupSnapshot.Status.PENDING,
                BackupSnapshot.Status.RUNNING,
                BackupSnapshot.Status.RESTORING,
            )
        )
        stale_before = timezone.now() - timedelta(hours=24)
        active.filter(updated_at__lt=stale_before).update(
            status=BackupSnapshot.Status.FAILED,
            error_message=str(_("The background job did not finish within 24 hours.")),
            completed_at=timezone.now(),
        )
        return active.filter(updated_at__gte=stale_before).exists()

    def _context(self, request, title, form):
        return {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": title,
            "form": form,
            "media": self.media + form.media,
            "back_url": reverse("admin:backup_manager_backupsnapshot_changelist"),
        }

    def create_backup_view(self, request):
        self._require_superuser(request)
        if request.method == "POST":
            form = CreateBackupForm(request.POST)
            if form.is_valid():
                if self._active_job_exists():
                    form.add_error(None, _("Another backup or restore job is already running."))
                else:
                    snapshot = BackupSnapshot.objects.create(
                        description=form.cleaned_data["description"],
                        created_by=request.user,
                    )
                    try:
                        spawn_backup_job(
                            "create_full_backup",
                            snapshot.pk,
                            form.cleaned_data["password"],
                        )
                    except BackupJobError as error:
                        snapshot.status = BackupSnapshot.Status.FAILED
                        snapshot.error_message = str(error)
                        snapshot.completed_at = timezone.now()
                        snapshot.save()
                        form.add_error(None, str(error))
                    else:
                        messages.success(
                            request,
                            _("Full encrypted backup has started. Refresh the list to see its status."),
                        )
                        return redirect("admin:backup_manager_backupsnapshot_changelist")
        else:
            form = CreateBackupForm()
        return render(
            request,
            "admin/backup_manager/backupsnapshot/create_backup.html",
            self._context(request, _("Create full backup"), form),
        )

    def restore_backup_view(self, request):
        self._require_superuser(request)
        initial = {}
        if request.GET.get("snapshot"):
            initial["snapshot"] = request.GET["snapshot"]
        if request.method == "POST":
            form = RestoreBackupForm(request.POST, request.FILES)
            if form.is_valid():
                if self._active_job_exists():
                    form.add_error(None, _("Another backup or restore job is already running."))
                else:
                    snapshot = form.cleaned_data.get("snapshot")
                    try:
                        if form.cleaned_data.get("uploaded_backup"):
                            snapshot = import_backup_archive(
                                form.cleaned_data["uploaded_backup"],
                                form.cleaned_data["password"],
                                created_by=request.user,
                                description=form.cleaned_data["description"],
                            )
                        snapshot.status = BackupSnapshot.Status.RESTORING
                        snapshot.save(update_fields=("status", "updated_at"))
                        spawn_backup_job(
                            "restore_full_backup",
                            snapshot.pk,
                            form.cleaned_data["password"],
                        )
                    except (BackupArchiveError, BackupJobError) as error:
                        if snapshot:
                            snapshot.status = BackupSnapshot.Status.FAILED
                            snapshot.error_message = str(error)
                            snapshot.completed_at = timezone.now()
                            snapshot.save()
                        form.add_error(None, str(error))
                    else:
                        messages.warning(
                            request,
                            _("Restore has started. The administration site may be temporarily unavailable."),
                        )
                        return redirect("admin:backup_manager_backupsnapshot_changelist")
        else:
            form = RestoreBackupForm(initial=initial)
        return render(
            request,
            "admin/backup_manager/backupsnapshot/restore_backup.html",
            self._context(request, _("Restore full backup"), form),
        )

    def _safe_archive(self, obj):
        path = obj.archive_file
        if not path or not path.is_file():
            raise Http404
        root = (
            Path(obj.storage_root).expanduser().resolve()
            if obj.storage_root
            else BackupSettings.get_solo().resolved_backup_directory
        )
        try:
            path.relative_to(root)
        except ValueError as error:
            raise SuspiciousFileOperation from error
        return path

    def download_backup_view(self, request, object_id):
        self._require_superuser(request)
        obj = self.get_object(request, str(object_id))
        if not obj or obj.status != BackupSnapshot.Status.COMPLETED:
            raise Http404
        path = self._safe_archive(obj)
        return FileResponse(path.open("rb"), as_attachment=True, filename=obj.archive_name)

    def verify_backup_view(self, request, object_id):
        self._require_superuser(request)
        obj = self.get_object(request, str(object_id))
        if not obj:
            raise Http404
        if request.method == "POST":
            form = VerifyBackupForm(request.POST)
            if form.is_valid():
                try:
                    verify_backup_archive(obj, form.cleaned_data["password"], full=True)
                except BackupArchiveError as error:
                    form.add_error(None, str(error))
                else:
                    messages.success(request, _("Backup ZIP and all encrypted files are valid."))
                    return redirect("admin:backup_manager_backupsnapshot_changelist")
        else:
            form = VerifyBackupForm()
        context = self._context(request, _("Verify backup"), form)
        context["snapshot"] = obj
        return render(
            request,
            "admin/backup_manager/backupsnapshot/verify_backup.html",
            context,
        )

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()
