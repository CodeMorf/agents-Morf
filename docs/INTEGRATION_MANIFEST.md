# Integration manifest

`GET /api/v1/agents/{id}/integration-manifest`

Downloadable JSON for customer engineers. **No secrets.**

Includes:

- `agent_id`, `slug`, `version`
- `api_base_url`
- `required_scopes` (`chat:write`, `tools:result`)
- `required_tools` + `tool_schemas`
- `tool_result_endpoint`
- `example_requests`: curl, Python, JavaScript, PHP (placeholders `am_YOUR_KEY`)
- `execution_mode_default`: `client`

Agents Morf Terminal can export the same document via **Manifest**.
