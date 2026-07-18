# Changelog

## 0.2.0 (ongoing on `architecture-v0.2`)

### Docs

- Full docs index (`docs/README.md`).
- New: Terminal, Platform tools (web/fetch/SSH/workspace), Studio runtime, Ops runbook.
- Expanded: Architecture, API, Deployment (phase1 VPS), Security, Grok parity.

### Studio agent behavior

- Morf Terminal playground (`/terminal`) with tool inspector and 90s abort.
- Prefetch web search + `fetch_url` for domains (`ver allsender.tech`).
- Prefetch SSH test + remote explore; ops report without echoing passwords.
- Fallback reports when provider returns 502 but tools already succeeded.
- Workspace sandbox tools aligned with Grok Build tool kinds.
- Agent Builder + 10 official templates + tool-results continuation.

### Platform baseline

- Reframed Agents Morf as the centralized AI control plane consumed by external product backends.
- Removed SMTP2GO and domain-specific lead, reservation, menu, order and call engines from the platform core.
- Added scoped durable memory and automatic memory extraction.
- Added Qdrant semantic indexing with lexical fallback.
- Added knowledge bases and document chunking.
- Added behavioral training datasets, examples and evaluation endpoint.
- Added agent version publishing.
- Added generic client/server tool registry and execution logs.
- Added revocable API keys for external products.
- Added OpenAI-style chat endpoint with tool calls and SSE mode.
- Added optional restricted Grok Build binary adapter without modifying Grok Build source.
- Rebuilt the React/Vite interface around Agents, Studio, Memory, Knowledge, Training, Tools, Providers and API keys.
- Staging stack `agentsmorfv02` on dedicated VPS path + exclusive domain cutover docs.

## 0.1.0

- Initial executable platform foundation.
