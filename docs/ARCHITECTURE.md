# Agents Morf architecture

## Purpose

Agents Morf is a centralized AI agent control plane deployed on `agent.codemorf.tech`. Other products consume it through API keys and keep their own operational databases and integrations.

## Runtime request flow

1. Authenticate a dashboard user or external API key.
2. Resolve the organization and agent.
3. Load the published agent configuration.
4. Retrieve scoped memory for the agent, end user and conversation.
5. Retrieve approved knowledge chunks linked to the agent.
6. Inject curated behavioral training examples.
7. Load the tools linked to the agent.
8. Choose the preferred provider and fallback order.
9. Generate a response or a structured tool request.
10. Execute an approved server tool, or return a client tool call to the product backend.
11. Persist messages and usage.
12. Queue safe memory extraction.

## Product boundary

Agents Morf does not contain restaurant, email, calendar, order or payment engines. Those services expose tool contracts to the agent platform.

Example:

```text
Restaurant customer
       │
Restaurant backend / channel adapter
       │  POST /chat/completions
       ▼
Agents Morf
       │  tool call: restaurant.check_availability
       ▼
Restaurant backend executes against its own database
       │  tool result
       ▼
Agents Morf creates the customer-facing answer
```

## Memory

PostgreSQL is the source of truth. Qdrant stores semantic vectors when embedding services are available. Retrieval combines semantic results with a lexical fallback.

Scopes:

- organization: shared rules and facts;
- agent: agent-specific context;
- end_user: durable facts tied to the external caller's stable user ID;
- conversation: context limited to one conversation.

## Training

Behavior is assembled from versioned instructions, training examples, knowledge and memory. Training examples are few-shot examples injected into the prompt. Evaluation runs compare actual answers with expected answers.

## Tools

Tools are generic contracts:

- `client`: return the call to the caller for execution;
- `server`: call a protected HTTPS API from Agents Morf.

The caller remains the system of record. Every tool call has an execution status and audit trail.

## Grok Build

Grok Build remains an independent program. The optional adapter launches its installed binary using restricted headless mode. The upstream Rust source is not modified and the provider is disabled by default.


## Learning loop

Feedback is stored separately from training data. Only reviewed corrections are promoted into behavioral examples, preventing silent learning from untrusted customer input.
