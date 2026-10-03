"""Database-specific backup and restore adapters.

The ZIP manifest records the adapter and dump format. Credentials are always
read from the active Django DATABASES configuration and are never written to
the archive or command line when the native tool supports an environment
variable.
"""

import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

from django.db import connections


class DatabaseBackupError(RuntimeError):
    pass


def _run(command, *, env=None, stdin=None, stdout=None):
    try:
        subprocess.run(
            command,
            check=True,
            env=env,
            stdin=stdin,
            stdout=stdout,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise DatabaseBackupError(f"Required database tool is not installed: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip() if error.stderr else ""
        raise DatabaseBackupError(detail or f"Database command failed: {command[0]}") from error


def _required_executable(*names):
    for name in names:
        executable = shutil.which(name)
        if executable:
            return executable
    raise DatabaseBackupError(f"Required database tool is not installed: {' or '.join(names)}")


class BaseDatabaseAdapter:
    adapter_name = "base"
    dump_format = "unknown"
    extension = ".dump"

    def __init__(self, alias="default"):
        self.alias = alias
        self.connection = connections[alias]
        self.config = self.connection.settings_dict

    @property
    def vendor(self):
        return self.connection.vendor

    def manifest(self, dump_name):
        return {
            "alias": self.alias,
            "vendor": self.vendor,
            "adapter": self.adapter_name,
            "format": self.dump_format,
            "dump_file": dump_name,
            "database_name": Path(str(self.config.get("NAME") or "")).name,
        }

    def create_dump(self, destination):
        raise NotImplementedError

    def restore_dump(self, source, manifest):
        raise NotImplementedError


class SQLiteAdapter(BaseDatabaseAdapter):
    adapter_name = "sqlite"
    dump_format = "sqlite3"
    extension = ".sqlite3"

    def create_dump(self, destination):
        destination = Path(destination)
        self.connection.ensure_connection()
        target = sqlite3.connect(destination)
        try:
            self.connection.connection.backup(target)
        finally:
            target.close()
        check = sqlite3.connect(destination)
        try:
            result = check.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            check.close()
        if result != "ok":
            raise DatabaseBackupError(f"SQLite integrity check failed: {result}")

    def restore_dump(self, source, manifest):
        source = Path(source)
        check = sqlite3.connect(source)
        try:
            result = check.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            check.close()
        if result != "ok":
            raise DatabaseBackupError(f"SQLite backup is invalid: {result}")

        target = Path(self.config["NAME"]).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        incoming = target.with_name(f".{target.name}.restore")
        shutil.copy2(source, incoming)
        connections.close_all()
        os.replace(incoming, target)


class PostgreSQLAdapter(BaseDatabaseAdapter):
    adapter_name = "postgresql"
    dump_format = "postgresql-custom"
    extension = ".pgdump"

    def _environment(self):
        environment = os.environ.copy()
        if self.config.get("PASSWORD"):
            environment["PGPASSWORD"] = str(self.config["PASSWORD"])
        return environment

    def _connection_args(self):
        args = []
        if self.config.get("HOST"):
            args += ["--host", str(self.config["HOST"])]
        if self.config.get("PORT"):
            args += ["--port", str(self.config["PORT"])]
        if self.config.get("USER"):
            args += ["--username", str(self.config["USER"])]
        return args

    def create_dump(self, destination):
        executable = _required_executable("pg_dump")
        command = [
            executable,
            "--format=custom",
            "--no-password",
            "--file",
            str(destination),
            *self._connection_args(),
            str(self.config["NAME"]),
        ]
        _run(command, env=self._environment())

    def restore_dump(self, source, manifest):
        self.connection.close()
        executable = _required_executable("pg_restore")
        command = [
            executable,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "--no-password",
            *self._connection_args(),
            "--dbname",
            str(self.config["NAME"]),
            str(source),
        ]
        _run(command, env=self._environment())


class MySQLAdapter(BaseDatabaseAdapter):
    adapter_name = "mysql"
    dump_format = "mysql-sql"
    extension = ".sql"

    def _environment(self):
        environment = os.environ.copy()
        if self.config.get("PASSWORD"):
            environment["MYSQL_PWD"] = str(self.config["PASSWORD"])
        return environment

    def _connection_args(self):
        args = []
        if self.config.get("HOST"):
            args += ["--host", str(self.config["HOST"])]
        if self.config.get("PORT"):
            args += ["--port", str(self.config["PORT"])]
        if self.config.get("USER"):
            args += ["--user", str(self.config["USER"])]
        return args

    def create_dump(self, destination):
        executable = _required_executable("mariadb-dump", "mysqldump")
        command = [
            executable,
            "--single-transaction",
            "--add-drop-database",
            "--routines",
            "--triggers",
            "--events",
            "--hex-blob",
            "--default-character-set=utf8mb4",
            *self._connection_args(),
            "--databases",
            str(self.config["NAME"]),
        ]
        with Path(destination).open("wb") as output:
            _run(command, env=self._environment(), stdout=output)

    def restore_dump(self, source, manifest):
        self.connection.close()
        executable = _required_executable("mariadb", "mysql")
        command = [
            executable,
            "--default-character-set=utf8mb4",
            *self._connection_args(),
        ]
        with Path(source).open("rb") as input_file:
            _run(command, env=self._environment(), stdin=input_file)


class MicrosoftSQLServerAdapter(BaseDatabaseAdapter):
    adapter_name = "mssql"
    dump_format = "mssql-bacpac"
    extension = ".bacpac"

    def _connection_string(self, *, database=None):
        host = str(self.config.get("HOST") or "localhost")
        port = self.config.get("PORT")
        server = f"{host},{port}" if port else host
        parts = [
            f"Server={server}",
            f"Initial Catalog={database or self.config['NAME']}",
            "TrustServerCertificate=True",
        ]
        if self.config.get("USER"):
            parts.extend(
                [
                    f"User ID={self.config['USER']}",
                    f"Password={self.config.get('PASSWORD') or ''}",
                ]
            )
        else:
            parts.append("Integrated Security=True")
        return ";".join(parts)

    def create_dump(self, destination):
        executable = _required_executable("sqlpackage")
        _run(
            [
                executable,
                "/Action:Export",
                f"/SourceConnectionString:{self._connection_string()}",
                f"/TargetFile:{destination}",
                "/Quiet:True",
            ]
        )

    def restore_dump(self, source, manifest):
        self.connection.close()
        sqlcmd = _required_executable("sqlcmd")
        sqlpackage = _required_executable("sqlpackage")
        database_name = str(self.config["NAME"])
        escaped_name = database_name.replace("]", "]]")
        escaped_literal = database_name.replace("'", "''")
        host = str(self.config.get("HOST") or "localhost")
        if self.config.get("PORT"):
            host = f"{host},{self.config['PORT']}"
        environment = os.environ.copy()
        command = [sqlcmd, "-S", host, "-d", "master", "-b"]
        if self.config.get("USER"):
            command += ["-U", str(self.config["USER"])]
            environment["SQLCMDPASSWORD"] = str(self.config.get("PASSWORD") or "")
        else:
            command.append("-E")
        command += [
            "-Q",
            (
                f"IF DB_ID(N'{escaped_literal}') IS NOT NULL "
                f"BEGIN ALTER DATABASE [{escaped_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
                f"DROP DATABASE [{escaped_name}]; END"
            ),
        ]
        _run(command, env=environment)
        _run(
            [
                sqlpackage,
                "/Action:Import",
                f"/TargetConnectionString:{self._connection_string()}",
                f"/SourceFile:{source}",
                "/Quiet:True",
            ]
        )


ADAPTERS = {
    "sqlite": SQLiteAdapter,
    "postgresql": PostgreSQLAdapter,
    "postgres": PostgreSQLAdapter,
    "mysql": MySQLAdapter,
    "mariadb": MySQLAdapter,
    "mssql": MicrosoftSQLServerAdapter,
    "microsoft": MicrosoftSQLServerAdapter,
    "sql_server": MicrosoftSQLServerAdapter,
}


def get_database_adapter(alias="default", *, expected_adapter=None):
    vendor = connections[alias].vendor.lower()
    adapter_class = ADAPTERS.get(vendor)
    if adapter_class is None:
        raise DatabaseBackupError(
            f"Unsupported database vendor '{vendor}'. Supported vendors: SQLite, PostgreSQL, MySQL/MariaDB and Microsoft SQL Server."
        )
    adapter = adapter_class(alias)
    if expected_adapter and adapter.adapter_name != expected_adapter:
        raise DatabaseBackupError(
            f"Backup database adapter '{expected_adapter}' does not match the configured '{adapter.adapter_name}' database."
        )
    return adapter
