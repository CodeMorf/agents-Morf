from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from app.core.config import settings


class ProviderError(RuntimeError):
    pass


@dataclass
class ProviderConfig:
    kind: str
    name: str
    base_url: str
    model: str
    api_key: str | None
    settings: dict[str, Any] = field(default_factory=dict)


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
    if config.kind == "grok_build":
        return await _grok_build(config, messages, temperature, max_tokens)
    raise ProviderError(f"Unsupported provider kind: {config.kind}")


async def stream_complete(
    config: ProviderConfig, messages: list[dict], temperature: float, max_tokens: int
) -> AsyncIterator[str]:
    if config.kind == "openai_compatible":
        async for chunk in _stream_openai_compatible(config, messages, temperature, max_tokens):
            yield chunk
        return
    if config.kind == "ollama":
        async for chunk in _stream_ollama(config, messages, temperature, max_tokens):
            yield chunk
        return
    result = await complete(config, messages, temperature, max_tokens)
    for index in range(0, len(result.content), 80):
        yield result.content[index : index + 80]


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
        content=data["choices"][0]["message"].get("content") or "",
        model=data.get("model", config.model),
        provider=config.name,
        usage=data.get("usage", {}),
    )


async def _stream_openai_compatible(config, messages, temperature, max_tokens):
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{config.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": config.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            },
        ) as response:
            if response.is_error:
                body = await response.aread()
                raise ProviderError(
                    f"{config.name}: HTTP {response.status_code}: {body.decode(errors='ignore')[:300]}"
                )
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                    content = data["choices"][0].get("delta", {}).get("content")
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue
                if content:
                    yield content


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
    text = "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    )
    usage_data = data.get("usage", {})
    usage = {
        "prompt_tokens": usage_data.get("input_tokens", 0),
        "completion_tokens": usage_data.get("output_tokens", 0),
        "total_tokens": usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
    }
    return ProviderResult(
        content=text, model=data.get("model", config.model), provider=config.name, usage=usage
    )


async def _ollama(config, messages, temperature, max_tokens):
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{config.base_url.rstrip('/')}/api/chat",
            json={
                "model": config.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
        )
    if response.is_error:
        raise ProviderError(f"Ollama: HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    usage = {
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "completion_tokens": data.get("eval_count", 0),
        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
    }
    return ProviderResult(
        content=data.get("message", {}).get("content", ""),
        model=data.get("model", config.model),
        provider=config.name,
        usage=usage,
    )


async def _stream_ollama(config, messages, temperature, max_tokens):
    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST",
            f"{config.base_url.rstrip('/')}/api/chat",
            json={
                "model": config.model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
        ) as response:
            if response.is_error:
                body = await response.aread()
                raise ProviderError(
                    f"Ollama: HTTP {response.status_code}: {body.decode(errors='ignore')[:300]}"
                )
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = data.get("message", {}).get("content")
                if content:
                    yield content
                if data.get("done"):
                    break


def build_grok_build_command(config: ProviderConfig, messages: list[dict]) -> tuple[list[str], str]:
    prompt = "\n".join(f"{message['role']}: {message['content']}" for message in messages)
    binary = str(config.settings.get("binary_path") or settings.grok_build_binary)
    cwd = str(config.settings.get("cwd") or settings.grok_build_cwd)
    model = config.model or settings.grok_build_model
    disallowed = (
        "run_terminal_cmd,grep,read_file,search_replace,list_dir,web_search,web_fetch,"
        "todo_write,task,Agent"
    )
    command = [
        binary,
        "-p",
        prompt,
        "-m",
        model,
        "--cwd",
        cwd,
        "--output-format",
        "json",
        "--disallowed-tools",
        disallowed,
        "--max-turns",
        str(config.settings.get("max_turns", 4)),
        "--rules",
        (
            "You are running as an optional provider inside Agents Morf. "
            "Do not edit files, execute tools, inspect repositories, or change Grok Build source. "
            "Return only the requested assistant response."
        ),
    ]
    return command, model


async def _grok_build(config, messages, temperature, max_tokens):
    del temperature, max_tokens
    if not settings.grok_build_enabled:
        raise ProviderError("Grok Build integration is disabled")
    cmd, model = build_grok_build_command(config, messages)
    binary = cmd[0]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ProviderError(f"Grok Build binary not found: {binary}") from exc
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=int(config.settings.get("timeout", settings.grok_build_timeout_seconds)),
        )
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise ProviderError("Grok Build timed out") from exc
    if proc.returncode != 0:
        raise ProviderError(f"Grok Build failed: {stderr.decode(errors='ignore')[:500]}")
    try:
        data = json.loads(stdout.decode())
    except json.JSONDecodeError as exc:
        raise ProviderError("Grok Build returned invalid JSON") from exc
    return ProviderResult(
        content=data.get("text", ""),
        model=model,
        provider=config.name,
        usage={},
    )
