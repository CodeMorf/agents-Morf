"""Tests for hybrid model router (CPU protection / external-first chat)."""
from dataclasses import dataclass

from app.services.hybrid_router import TaskClass, decide, order_configs


@dataclass
class FakeCfg:
    kind: str
    name: str


def test_prefer_local_false_production_conversation():
    d = decide(TaskClass.conversation, production_conversation=True, force_local=False)
    assert d.prefer_local is False
    assert d.local_allowed is False
    assert "external" in d.reason or "production" in d.reason


def test_force_external():
    d = decide(TaskClass.embedding, force_external=True)
    assert d.prefer_local is False
    assert d.reason == "force_external"


def test_cpu_ge_60_rejects_local():
    # inject high CPU by using local_busy or threshold 0
    d2 = decide(
        TaskClass.summary,
        production_conversation=False,
        cpu_threshold=0.0,  # any real cpu >= 0 blocks
        local_busy=False,
    )
    # On Windows getloadavg may be None; local_busy path is reliable
    d3 = decide(
        TaskClass.summary,
        production_conversation=False,
        local_busy=True,
    )
    assert d3.prefer_local is False
    assert d3.reason == "local_inference_busy"
    # When CPU available and threshold 0: if cpu is not None, prefer_local False
    if d2.cpu_percent is not None:
        assert d2.prefer_local is False
        assert "cpu_" in d2.reason


def test_order_configs_external_first_for_chat():
    configs = [
        FakeCfg("ollama", "Ollama"),
        FakeCfg("openai_compatible", "Groq"),
        FakeCfg("openai_compatible", "OpenAI"),
    ]
    d = decide(TaskClass.conversation, production_conversation=True)
    ordered = order_configs(configs, d)
    assert ordered[0].name == "Groq"
    assert ordered[-1].name == "Ollama"


def test_fallback_order_when_external_present_and_local_last():
    """Simulate Groq disabled: only ollama remains usable still ordered last if mixed."""
    configs = [
        FakeCfg("ollama", "Ollama"),
        FakeCfg("openai_compatible", "Groq"),
    ]
    d = decide(TaskClass.conversation, production_conversation=True)
    ordered = order_configs(configs, d)
    # Groq still first when present (prefer_local false)
    assert ordered[0].kind == "openai_compatible"
    # If only ollama (Groq disabled/removed), ollama is only option
    only_local = order_configs([FakeCfg("ollama", "Ollama")], d)
    assert len(only_local) == 1
    assert only_local[0].name == "Ollama"


def test_light_task_may_prefer_local_when_not_busy():
    d = decide(
        TaskClass.embedding,
        production_conversation=False,
        local_busy=False,
        cpu_threshold=100.0,  # never trip on cpu
    )
    assert d.prefer_local is True
    assert d.local_allowed is True


def test_force_external_blocks_local_for_chat_policy():
    d = decide(TaskClass.conversation, force_external=True)
    assert d.prefer_local is False
    assert d.local_allowed is False


def test_is_local_kind():
    from app.services.hybrid_router import is_local_kind

    assert is_local_kind("ollama") is True
    assert is_local_kind("openai_compatible") is False
