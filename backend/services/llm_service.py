import httpx
from openai import AsyncOpenAI
from backend.config import settings


def get_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=httpx.Timeout(settings.llm_timeout, connect=10.0),
    )


async def chat_completion(
    messages: list[dict],
    *,
    json_mode: bool = False,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    client = get_llm_client()
    kwargs: dict = {
        "model": settings.llm_model,
        "messages": messages,
        "max_tokens": max_tokens or settings.max_tokens,
        "temperature": temperature or settings.temperature,
    }
    if json_mode:
        # Some endpoints support json_object, others json_schema, some neither.
        # We skip response_format for max compatibility and parse JSON from response.
        pass

    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def chat_completion_stream(
    messages: list[dict],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
):
    """Yield content chunks via SSE-style streaming."""
    client = get_llm_client()
    stream = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        max_tokens=max_tokens or settings.max_tokens,
        temperature=temperature or settings.temperature,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content
