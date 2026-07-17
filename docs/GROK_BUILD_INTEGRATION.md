# Grok Build integration

## Safety principle

The Grok Build Rust source is not modified by Agents Morf. It remains a separate upstream codebase and can be upgraded or rebuilt independently.

Agents Morf supports an optional provider adapter that launches an installed `grok` binary in headless JSON mode. This avoids editing the generated Grok Build workspace and prevents business-platform changes from breaking the coding agent.

## Enable

Build or install Grok Build separately, then make the binary available to the backend container or host.

```env
GROK_BUILD_ENABLED=true
GROK_BUILD_BINARY=/usr/local/bin/grok
GROK_BUILD_CWD=/workspace
GROK_BUILD_MODEL=grok-build
```

Create a provider with kind `grok_build`.

## Restrictions

The adapter starts Grok Build with its file, terminal, search, web and subagent tools disabled. It is treated as a text model provider, not as the generic business tool executor.

For rich coding-agent integration, use Grok Build's ACP mode in a dedicated service. Do not expose an unrestricted coding agent to public customer requests.

## Recommended use

- internal programming assistants;
- repository analysis;
- controlled CodeMorf engineering workflows.

For customer-facing sales or support agents, use Ollama or cloud chat-model providers with Agents Morf's generic tool registry.
