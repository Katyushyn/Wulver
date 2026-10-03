from django.core.management.base import BaseCommand

from apps.theme_manager.services.template_components import sync_template_components


class Command(BaseCommand):
    help = "Create or update the built-in Wulver template component presets."

    def handle(self, *args, **options):
        result = sync_template_components(stdout=self.stdout)

        self.stdout.write(
            self.style.SUCCESS(
                "Done. "
                f"{result['created']} created, "
                f"{result['updated']} updated."
            )
        )
