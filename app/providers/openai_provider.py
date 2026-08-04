from app.providers.openai_compatible import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    key = "openai"
    default_base_url = "https://api.openai.com/v1"
