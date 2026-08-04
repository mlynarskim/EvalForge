from app.providers.openai_compatible import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    key = "openrouter"
    default_base_url = "https://openrouter.ai/api/v1"
    extra_headers = {"HTTP-Referer": "https://localhost/evalforge", "X-Title": "EvalForge"}
