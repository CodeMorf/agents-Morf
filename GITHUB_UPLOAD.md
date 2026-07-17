# Updating the GitHub repository safely

Repository: `https://github.com/CodeMorf/agents-Morf.git`

Use a feature branch instead of forcing `main`:

```bash
git checkout -b architecture-v0.2
git add .
git commit -m "Decouple product backends and add memory training platform"
git push -u origin architecture-v0.2
```

Open a pull request, wait for CI, review the diff and merge only after backend tests and the React/Vite build succeed.

Suggested description:

```text
Provider-neutral, multi-tenant AI agent API and Studio with memory, RAG, tools, training, evaluations and model routing.
```

Suggested topics:

```text
ai-agents autonomous-agents fastapi react vite multi-tenant llm ollama rag agent-memory tool-calling openai-compatible
```

Never upload `.env`, API keys, customer records or the Grok Build source archive.
