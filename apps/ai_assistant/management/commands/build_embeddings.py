from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.ai_assistant.models import AssistantProfile, KnowledgeChunk
from apps.ai_assistant.services.embeddings import build_chunk_embedding


class Command(BaseCommand):
    help = "Build embeddings for knowledge chunks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Rebuild embeddings even if they already exist",
        )

    def handle(self, *args, **options):
        assistant = AssistantProfile.objects.order_by("pk").first()
        if not assistant:
            self.stderr.write(self.style.ERROR("No AssistantProfile found"))
            return

        chunks = KnowledgeChunk.objects.filter(is_active=True)

        if not options["force"]:
            chunks = chunks.filter(
                Q(embedding__isnull=True) |
                Q(embedding=[])
            )

        total = chunks.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No chunks to process"))
            return

        created = 0
        failed = 0

        for chunk in chunks:
            try:
                build_chunk_embedding(chunk, assistant)
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"OK: {chunk.title}")
                )

            except Exception as e:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"FAILED: {chunk.title} - {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Processed: {created}, failed: {failed}"
            )
        )
