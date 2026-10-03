# Wulver Backup Manager

Backup Manager creates an AES-256 encrypted ZIP containing:

- the complete `BASE_DIR` tree, including dotfiles, `.git`, local virtual environments and collected static files;
- `STATIC_ROOT`, `MEDIA_ROOT`, template directories and configured additional paths when they live outside `BASE_DIR`;
- empty directories, safe relative symlinks, file permissions and timestamps;
- a consistent native dump of the Django `default` database;
- an encrypted `manifest.json` describing logical roots and the database adapter.

The backup directory defaults to a private sibling of `BASE_DIR` and must not be inside any backed-up root. ZIP files are mode `0600`; the directory is mode `0700`. Passwords are supplied for each create, verify or restore operation and are never stored in Django models or the ZIP.

## Database tools

SQLite uses Python's online backup API and needs no external command. Other engines require their native tools to be available to the Django operating-system account:

- PostgreSQL: `pg_dump` and `pg_restore`;
- MySQL: `mysqldump` and `mysql`;
- MariaDB: `mariadb-dump` and `mariadb` (MySQL-compatible names are accepted as fallback);
- Microsoft SQL Server: `sqlpackage` for BACPAC export/import and `sqlcmd` for replacing the target database.

Database credentials are read from the active Django `DATABASES` setting. PostgreSQL and MySQL/MariaDB passwords are passed to native tools through their supported environment variables rather than command-line arguments.

## Restore behavior

Restore validates the ZIP, password, SHA-256 checksum, manifest, every encrypted member and all paths before replacement. Logical roots are mapped to the current server's `BASE_DIR`, `STATIC_ROOT`, `MEDIA_ROOT` and template configuration, so paths may differ between cPanel and a VPS. The current backup storage configuration is preserved when the database is restored.

Restore is destructive and runs as a detached management command. A Passenger-compatible `tmp/restart.txt` marker is touched after success; other application servers may require their own supervisor restart policy.
