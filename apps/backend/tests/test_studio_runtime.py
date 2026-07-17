"""Studio runtime: platform tools + client tool simulation continue."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_studio.db")
os.environ.setdefault("AUTO_CREATE_SCHEMA", "true")

from app.services.builtin_tools import simulate_client_tool_result
from app.services.tools import parse_tool_call


def test_parse_tool_call_with_prose():
    content = (
        'Voy a calcularlo.\n'
        '{"type":"tool_call","tool":"platform.calculate",'
        '"arguments":{"expression":"100*0.15"},"reason":"comision"}'
    )
    parsed = parse_tool_call(content)
    assert parsed is not None
    assert parsed.name == "platform.calculate"
    assert parsed.arguments["expression"] == "100*0.15"


def test_simulate_sales_price():
    result = simulate_client_tool_result("sales.check_price", {"product_id": "p1"})
    assert result["simulated"] is True
    assert result["price"] == 49.99
