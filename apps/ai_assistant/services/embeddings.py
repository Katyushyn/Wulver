from django.utils import timezone

from apps.ai_assistant.services.providers import get_provider_client


def build_chunk_embedding(chunk, assistant):
    client = get_provider_client(assistant)

    text = f"{chunk.title}\n\n{chunk.content}"

    embedding = client.embedding(text)

    chunk.embedding = embedding
    chunk.embedding_model = assistant.embedding_model
    chunk.embedding_updated_at = timezone.now()

    chunk.save(
        update_fields=[
            "embedding",
            "embedding_model",
            "embedding_updated_at",
        ]
    )

    return chunk
