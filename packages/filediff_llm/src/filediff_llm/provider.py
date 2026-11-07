from __future__ import annotations

from openai import AsyncOpenAI


class OpenAICompatibleProvider:
    """LM Studio, OpenAI, or any other server that speaks the OpenAI chat API."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "lm-studio"
        self.model = model
        self.timeout = timeout
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)

    async def complete_json(self, system: str, user: str) -> tuple[str, dict]:
        response = await self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        usage = response.usage
        stats = {
            "promptTokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completionTokens": int(getattr(usage, "completion_tokens", 0) or 0),
        }
        return text, stats


async def list_models(base_url: str, api_key: str = "lm-studio") -> list[str]:
    client = AsyncOpenAI(api_key=api_key or "lm-studio", base_url=base_url.rstrip("/"), timeout=8.0)
    page = await client.models.list()
    names = [str(item.id) for item in page.data if getattr(item, "id", None)]
    return sorted(set(names))
