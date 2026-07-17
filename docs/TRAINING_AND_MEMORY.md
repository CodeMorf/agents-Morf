# Training, memory and continuous improvement

Agents Morf trains agent behavior without taking ownership of another product's operational data.

## Behavior stack

1. **System prompt** defines identity, limits and global behavior.
2. **Instructions** define the organization's operating policy.
3. **Published versions** snapshot a tested agent configuration.
4. **Training examples** provide approved input/output patterns.
5. **Knowledge bases** provide factual, versionable business content through RAG.
6. **Long-term memory** preserves safe facts and preferences by tenant, agent, end user or conversation.
7. **Human feedback** records positive/negative outcomes and corrections.
8. **Evaluations** run a dataset against an agent before publishing a new version.

This is controlled contextual training. It is not automatic provider fine-tuning. Provider fine-tuning can later be implemented behind the same agent API.

## Memory safety

PostgreSQL is the source of truth. Qdrant is the semantic retrieval index. Memory extraction rejects passwords, tokens, payment details, temporary requests and unsupported guesses. Product-specific records remain in the product backend and are accessed only through registered tools.

## Feedback loop

External products may submit feedback with an API key carrying `feedback:write`:

```http
POST /api/v1/feedback
Authorization: Bearer am_...
Content-Type: application/json
```

```json
{
  "agent_id": "...",
  "conversation_id": "...",
  "message_id": "...",
  "rating": -1,
  "category": "accuracy",
  "comment": "The plan limits were outdated",
  "correction": "The Professional plan includes 25 team members."
}
```

A developer can review the feedback and promote an approved correction into a training dataset. Nothing is learned silently from untrusted feedback.

## Release workflow

1. Update prompt, examples or knowledge.
2. Run `/api/v1/training/evaluate` on a curated dataset.
3. Review failed cases and tool behavior.
4. Publish an immutable agent version.
5. Deploy or select that version through the calling platform.
