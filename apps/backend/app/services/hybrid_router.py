"""Hybrid Model Router — protect the host from Ollama CPU saturation.

Policy (production VPS without GPU):
- Conversation / complex reasoning → cloud / external first
- Embeddings, classification, short extract, memory jobs → Ollama if CPU OK
- Max one local inference intent (enforced also via OLLAMA_NUM_PARALLEL=1)

This module does not install providers; it only orders them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class TaskClass(str, Enum):
    conversation = "conversation"
    reasoning = "reasoning"
    coding = "coding"
    tool_calling = "tool_calling"
    embedding = "embedding"
    classification = "classification"
    extraction = "extraction"
    summary = "summary"
    memory = "memory"
    private = "private"
    background = "background"


LOCAL_KINDS = frozenset({"ollama", "vllm", "llamacpp"})
EXTERNAL_KINDS = frozenset(
    {
        "openai_compatible",
        "openai",
        "gemini",
        "anthropic",
        "groq",
        "openrouter",
        "mistral",
        "deepseek",
        "xai",
        "grok_build",
    }
)

# Tasks that MAY use local Ollama when CPU allows
LOCAL_OK_TASKS = frozenset(
    {
        TaskClass.embedding,
        TaskClass.classification,
        TaskClass.extraction,
        TaskClass.summary,
        TaskClass.memory,
        TaskClass.private,
        TaskClass.background,
    }
)


@dataclass
class RouteDecision:
    prefer_local: bool
    reason: str
    cpu_percent: float | None
    local_allowed: bool


def read_cpu_percent() -> float | None:
    """Best-effort 1-sample load-based CPU estimate (0-100)."""
    try:
        load1, _, _ = os.getloadavg()
        n = os.cpu_count() or 1
        return min(100.0, max(0.0, (load1 / n) * 100.0))
    except (AttributeError, OSError):
        return None


def decide(
    task: TaskClass | str,
    *,
    production_conversation: bool = True,
    force_local: bool = False,
    force_external: bool = False,
    cpu_threshold: float = 60.0,
    local_busy: bool = False,
) -> RouteDecision:
    task = TaskClass(task) if not isinstance(task, TaskClass) else task
    cpu = read_cpu_percent()

    if force_external:
        return RouteDecision(False, "force_external", cpu, False)
    if force_local:
        return RouteDecision(True, "force_local", cpu, True)

    # Production chat / complex work never defaults to Ollama on shared VPS
    if production_conversation and task in {
        TaskClass.conversation,
        TaskClass.reasoning,
        TaskClass.coding,
        TaskClass.tool_calling,
    }:
        return RouteDecision(
            False,
            "production_conversation_uses_external",
            cpu,
            False,
        )

    if task not in LOCAL_OK_TASKS:
        return RouteDecision(False, f"task_{task.value}_prefers_external", cpu, False)

    if local_busy:
        return RouteDecision(False, "local_inference_busy", cpu, False)

    if cpu is not None and cpu >= cpu_threshold:
        return RouteDecision(False, f"cpu_{cpu:.0f}_ge_{cpu_threshold:.0f}", cpu, False)

    return RouteDecision(True, f"task_{task.value}_local_ok", cpu, True)


def order_configs(
    configs: Sequence,
    decision: RouteDecision,
    *,
    kind_attr: str = "kind",
) -> list:
    """Reorder provider configs: external first or local first per decision."""

    def kind_of(c) -> str:
        return str(getattr(c, kind_attr, "") or "").lower()

    local: list = []
    external: list = []
    other: list = []
    for c in configs:
        k = kind_of(c)
        if k in LOCAL_KINDS or "ollama" in k:
            local.append(c)
        elif k in EXTERNAL_KINDS or k:
            external.append(c)
        else:
            other.append(c)

    if decision.prefer_local and decision.local_allowed:
        # local first, then external fallback
        return local + external + other
    # external first; local last (emergency only)
    return external + other + local


def is_local_kind(kind: str) -> bool:
    k = (kind or "").lower()
    return k in LOCAL_KINDS or "ollama" in k
