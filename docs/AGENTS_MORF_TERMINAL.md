# Agents Morf Terminal

Route: **`/terminal`**

## What it is

A **secure playground** to exercise the full agent loop (chat → tool_calls → simulated tool_results → continuation).

## What it is NOT

- Not a Linux terminal  
- Not PowerShell / Bash on the VPS  
- Not a remote shell into Agents Morf servers  
- Not real execution of customer business operations  

## Layout

| Panel | Content |
|-------|---------|
| Left | Organization context, agent, version, API key prefix, mode, `end_user_id`, external conversation id |
| Center | Conversation, tool call pills, composer |
| Right | Request/response JSON, provider/model/tokens/latency, Client Tool Simulator, copy curl/Python/JS, logs, download transcript/manifest |

## Client Tool Simulator

When the model returns `finish_reason: tool_calls`, pick a call and paste a mock JSON result. The UI posts to `POST /api/v1/tool-results` and the agent continues.

Example mock for `sales.check_price`:

```json
{ "price": 49.99, "currency": "USD" }
```

## Programming AI in Terminal

You may **simulate** list/read/patch/test results. Real code execution requires a future Agents Morf Desktop / authorized runner — not this Terminal.

## Safety

- JWT session or API key with `chat:write` / `tools:result`
- Tenant isolation
- No secrets in copied examples (`am_YOUR_KEY` placeholder)
