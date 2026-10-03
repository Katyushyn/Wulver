from openai import OpenAI
from django.conf import settings

from .base import BaseAIProvider


class OpenAIProvider(BaseAIProvider):
    def __init__(self, provider):
        super().__init__(provider)

        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=provider.provider_timeout_seconds,
            max_retries=provider.provider_max_retries,
        )
        self.last_embedding_tokens = 0

    def chat(self, messages, temperature=0.3):
        response = self.client.responses.create(
            model=self.provider.chat_model,
            input=messages,
            temperature=temperature,
            max_output_tokens=self.provider.max_output_tokens,
        )

        usage = getattr(response, "usage", None)

        return {
            "text": response.output_text,
            "raw": response,
            "prompt_tokens": getattr(usage, "input_tokens", None),
            "completion_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    def embedding(self, text):
        response = self.client.embeddings.create(
            model=self.provider.embedding_model,
            input=text,
        )

        usage = getattr(response, "usage", None)
        self.last_embedding_tokens = getattr(usage, "total_tokens", 0) or 0

        return response.data[0].embedding
