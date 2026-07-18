from app.core.security import generate_api_key, hash_api_key
from app.services.document_loader import extract_document_text
from app.services.memory import parse_memory_candidates
from app.services.providers import ProviderConfig, build_grok_build_command
from app.services.tools import parse_tool_call


def test_api_key_generation_and_hashing():
    raw, prefix = generate_api_key()
    assert raw.startswith("am_")
    assert raw.startswith(prefix)
    assert len(hash_api_key(raw)) == 64
    assert hash_api_key(raw) == hash_api_key(raw)


def test_tool_call_parser_accepts_strict_json():
    call = parse_tool_call(
        '{"type":"tool_call","tool":"calendar.reserve","arguments":{"slot":"10:00"}}'
    )
    assert call is not None
    assert call.name == "calendar.reserve"
    assert call.arguments["slot"] == "10:00"


def test_tool_call_parser_rejects_normal_text():
    assert parse_tool_call("I would like to call a tool.") is None


def test_memory_candidate_parser_filters_invalid_entries():
    parsed = parse_memory_candidates(
        '[{"content":"Customer prefers Spanish","scope":"end_user",'
        '"kind":"preference","importance":0.9}, {"bad":true}]'
    )
    assert len(parsed) == 1
    assert parsed[0]["content"] == "Customer prefers Spanish"
    assert parsed[0]["importance"] == 0.9


def test_grok_build_adapter_is_restricted():
    config = ProviderConfig(
        kind="grok_build",
        name="Grok Build",
        base_url="",
        model="grok-build",
        api_key=None,
        settings={"binary_path": "grok", "cwd": "/safe/workspace"},
    )
    command, model = build_grok_build_command(
        config, [{"role": "user", "content": "Explain this API contract"}]
    )
    assert model == "grok-build"
    assert "--output-format" in command
    disallowed = command[command.index("--disallowed-tools") + 1]
    for tool in ("run_terminal_cmd", "read_file", "search_replace", "web_fetch", "Agent"):
        assert tool in disallowed
    rules = command[command.index("--rules") + 1]
    assert "Do not edit files" in rules
    assert "change Grok Build source" in rules


def test_document_loader_text_csv_and_json():
    assert (
        extract_document_text("guide.md", "text/markdown", b"# Guide\nUse the API")
        == "# Guide\nUse the API"
    )
    assert "name | price" in extract_document_text("items.csv", "text/csv", b"name,price\nPlan,10")
    assert '"enabled": true' in extract_document_text(
        "settings.json", "application/json", b'{"enabled":true}'
    )
