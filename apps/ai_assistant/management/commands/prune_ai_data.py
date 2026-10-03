from django.core.management.base import BaseCommand

from apps.ai_assistant.models import AssistantProfile
from apps.ai_assistant.services.retention import prune_expired_ai_data


class Command(BaseCommand):
    help = "Delete AI assistant conversations, leads, and logs older than the configured retention period."

    def handle(self, *args, **options):
        assistant = AssistantProfile.objects.order_by("pk").first()
        if assistant is None:
            self.stdout.write("No AI assistant profile found.")
            return

        result = prune_expired_ai_data(assistant, force=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"Pruned {result['sessions']} session objects, {result['leads']} lead objects, and {result['logs']} log objects."
            )
        )
