from app.providers.openai_compatible import OpenAICompatibleProvider


class MistralProvider(OpenAICompatibleProvider):
    key = "mistral"
    default_base_url = "https://api.mistral.ai/v1"
