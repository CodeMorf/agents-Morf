from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ProviderError(RuntimeError):
    pass


@dataclass
class ProviderConfig:
    kind: str
    name: str
    base_url: str
    model: str
    api_key: str | None
    settings: dict[str, Any]


@dataclass
class ProviderResult:
    content: str
    model: str
    provider: str
    usage: dict[str, int]


async def complete(
    config: ProviderConfig, messages: list[dict], temperature: float, max_tokens: int
) -> ProviderResult:
    if config.kind == "openai_compatible":
        return await _openai_compatible(config, messages, temperature, max_tokens)
    if config.kind == "gemini":
        return await _gemini(config, messages, temperature, max_tokens)
    if config.kind == "anthropic":
        return await _anthropic(config, messages, temperature, max_tokens)
    if config.kind == "ollama":
        return await _ollama(config, messages, temperature, max_tokens)
    raise ProviderError(f"Unsupported provider kind: {config.kind}")


async def _openai_compatible(config, messages, temperature, max_tokens):
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{config.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": config.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
        )
    if response.is_error:
        raise ProviderError(f"{config.name}: HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    return ProviderResult(
        content=data["choices"][0]["message"]["content"],
        model=data.get("model", config.model),
        provider=config.name,
        usage=data.get("usage", {}),
    )


async def _gemini(config, messages, temperature, max_tokens):
    if not config.api_key:
        raise ProviderError("Gemini API key is missing")
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
        if m["role"] != "system"
    ]
    body = {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if system_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n".join(system_parts)}]}
    url = f"{config.base_url.rstrip('/')}/v1beta/models/{config.model}:generateContent"
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, params={"key": config.api_key}, json=body)
    if response.is_error:
        raise ProviderError(f"Gemini: HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    content = data["candidates"][0]["content"]["parts"][0]["text"]
    usage_meta = data.get("usageMetadata", {})
    usage = {
        "prompt_tokens": usage_meta.get("promptTokenCount", 0),
        "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
        "total_tokens": usage_meta.get("totalTokenCount", 0),
    }
    return ProviderResult(content=content, model=config.model, provider=config.name, usage=usage)


async def _anthropic(config, messages, temperature, max_tokens):
    if not config.api_key:
        raise ProviderError("Anthropic API key is missing")
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    anthropic_messages = [m for m in messages if m["role"] in {"user", "assistant"}]
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": config.model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": anthropic_messages,
    }
    if system:
        body["system"] = system
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{config.base_url.rstrip('/')}/v1/messages", headers=headers, json=body
        )
    if response.is_error:
        raise ProviderError(f"Anthropic: HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    usage_data = data.get("usage", {})
    return ProviderResult(
        content="".join(part.get("text", "") for part in data.get("content", [])),
        model=data.get("model", config.model),
        provider=config.name,
        usage={
            "prompt_tokens": usage_data.get("input_tokens", 0),
            "completion_tokens": usage_data.get("output_tokens", 0),
            "total_tokens": usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
        },
    )


async def _ollama(config, messages, temperature, max_tokens):
    body = {
        "model": config.model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(f"{config.base_url.rstrip('/')}/api/chat", json=body)
    if response.is_error:
        raise ProviderError(f"Ollama: HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    return ProviderResult(
        content=data.get("message", {}).get("content", ""),
        model=data.get("model", config.model),
        provider=config.name,
        usage={
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        },
    )
