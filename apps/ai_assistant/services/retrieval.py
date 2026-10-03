import math

from apps.ai_assistant.models import KnowledgeChunk


def cosine_similarity(vector_a, vector_b):
    dot = sum(a * b for a, b in zip(vector_a, vector_b))

    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0 or norm_b == 0:
        return 0

    return dot / (norm_a * norm_b)


def find_similar_chunks(question_embedding, limit=5, min_score=0.2):
    chunks = KnowledgeChunk.objects.filter(
        is_active=True,
        embedding__isnull=False,
    )

    results = []

    for chunk in chunks:
        similarity = cosine_similarity(question_embedding, chunk.embedding)

        final_score = similarity + (chunk.priority * 0.01)

        if final_score >= min_score:
            results.append((final_score, chunk))

    results.sort(key=lambda item: item[0], reverse=True)

    return results[:limit]