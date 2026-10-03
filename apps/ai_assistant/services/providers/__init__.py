from .openai_provider import OpenAIProvider


def get_provider_client(provider):
    if provider.provider_type == "openai":
        return OpenAIProvider(provider)

    raise ValueError(f"Unsupported provider type: {provider.provider_type}")