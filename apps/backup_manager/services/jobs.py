import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings

from apps.backup_manager.models import BackupSettings


class BackupJobError(RuntimeError):
    pass


def _write_password_file(password):
    root = BackupSettings.get_solo().resolved_backup_directory
    job_directory = root / ".jobs"
    job_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, path = tempfile.mkstemp(prefix="password-", dir=job_directory)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as password_file:
            password_file.write(password)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        Path(path).unlink(missing_ok=True)
        raise
    return Path(path)


def read_and_remove_password_file(path):
    password_path = Path(path).expanduser().resolve()
    jobs_root = (BackupSettings.get_solo().resolved_backup_directory / ".jobs").resolve()
    try:
        password_path.relative_to(jobs_root)
    except ValueError as error:
        raise BackupJobError("Invalid backup password file path.") from error
    try:
        return password_path.read_text(encoding="utf-8")
    finally:
        password_path.unlink(missing_ok=True)


def spawn_backup_job(command_name, snapshot_id, password):
    root = BackupSettings.get_solo().resolved_backup_directory
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    password_file = _write_password_file(password)
    log_directory = root / ".jobs"
    log_path = log_directory / f"{command_name}-{snapshot_id}.log"
    manage_py = Path(settings.BASE_DIR) / "manage.py"
    command = [
        sys.executable,
        str(manage_py),
        command_name,
        str(snapshot_id),
        "--password-file",
        str(password_file),
    ]
    try:
        log_handle = log_path.open("ab")
        subprocess.Popen(
            command,
            cwd=settings.BASE_DIR,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
        log_handle.close()
    except Exception as error:
        password_file.unlink(missing_ok=True)
        raise BackupJobError(str(error)) from error
    return log_path
