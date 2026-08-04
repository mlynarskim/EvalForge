from app.providers.openai_compatible import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    key = "ollama"
    default_base_url = "http://host.docker.internal:11434/v1"
