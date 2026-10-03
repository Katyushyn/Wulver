from pathlib import Path

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand


PROJECT_APPS = (
    "ai_assistant",
    "backup_manager",
    "blog_manager",
    "comments_manager",
    "core_manager",
    "theme_manager",
    "userprofile",
)


class Command(BaseCommand):
    help = (
        "Initialize a clean Wulver project: create current-model migrations, "
        "migrate the database, and sync built-in presets."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-makemigrations",
            action="store_true",
            help="Do not generate migrations before migrating.",
        )
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            help="Do not apply migrations.",
        )
        parser.add_argument(
            "--skip-components",
            action="store_true",
            help="Do not sync built-in template component presets.",
        )
        parser.add_argument(
            "--reset-migration-files",
            action="store_true",
            help=(
                "Delete Wulver app migration files before makemigrations. "
                "Use only for a clean starter deployment without an existing database."
            ),
        )

    def reset_project_migration_files(self):
        removed = 0

        for app_label in PROJECT_APPS:
            migrations_dir = Path(apps.get_app_config(app_label).path) / "migrations"

            if not migrations_dir.exists():
                continue

            init_file = migrations_dir / "__init__.py"
            init_file.touch(exist_ok=True)

            for migration_file in migrations_dir.glob("*.py"):
                if migration_file.name == "__init__.py":
                    continue

                migration_file.unlink()
                removed += 1

        self.stdout.write(f"Removed {removed} Wulver migration file(s).")

    def handle(self, *args, **options):
        if options["reset_migration_files"]:
            self.stdout.write("Resetting Wulver migration files...")
            self.reset_project_migration_files()

        if not options["skip_makemigrations"]:
            self.stdout.write("Generating clean migrations from current models...")
            call_command("makemigrations", interactive=False)

        if not options["skip_migrate"]:
            self.stdout.write("Applying migrations...")
            call_command("migrate", interactive=False)

        if not options["skip_components"]:
            self.stdout.write("Syncing built-in template components...")
            call_command("sync_template_components")

        self.stdout.write(self.style.SUCCESS("Wulver initialization complete."))
