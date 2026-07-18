# Client tool execution

## Default policy

`execution_mode = client` for template tools and preferred production integrations.

Agents Morf:

- Decides **which** tool and with **which** arguments  
- Returns structured `tool_calls`  
- Does **not** own customer DB side-effects  

Customer backend:

- Validates auth/business rules  
- Executes the operation  
- Posts `tool_result` (success/failed/rejected/timeout)  

Server-side tools remain optional, restricted, and off by default (`auto_tool_execution=false`).

## Chat response shape

```json
{
  "finish_reason": "tool_calls",
  "tool_calls": [
    {
      "id": "call_123",
      "name": "restaurant.check_availability",
      "arguments": { "date": "2026-07-25", "party_size": 4 },
      "execution_mode": "client",
      "requires_approval": false
    }
  ]
}
```

## Confirmation rule

Never claim order created, payment received, reservation confirmed, inventory reserved, or email sent until a **successful** tool_result is processed.
