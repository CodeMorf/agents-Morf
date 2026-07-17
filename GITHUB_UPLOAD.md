# Upload to GitHub

Repository:

```text
https://github.com/CodeMorf/agents-Morf.git
```

## Command line

Extract the ZIP, open a terminal inside the `agents-Morf` directory and run:

```bash
git init
git branch -M main
git add .
git commit -m "Initial Agents Morf platform"
git remote add origin https://github.com/CodeMorf/agents-Morf.git
git push -u origin main
```

If `origin` already exists:

```bash
git remote set-url origin https://github.com/CodeMorf/agents-Morf.git
git push -u origin main
```

## Repository presentation

Suggested GitHub description:

```text
Agents Morf — The Autonomous AI Agent Operating System for sales, reservations, restaurant operations, support and real-world business automation.
```

Suggested website:

```text
https://agent.codemorf.tech
```

Suggested topics:

```text
ai-agents autonomous-agents fastapi react vite multi-tenant llm ollama sales-automation restaurant-automation reservations openai-compatible
```

With GitHub CLI:

```bash
gh repo edit CodeMorf/agents-Morf \
  --description "Agents Morf — The Autonomous AI Agent Operating System for sales, reservations, restaurant operations, support and real-world business automation." \
  --homepage "https://agent.codemorf.tech" \
  --add-topic ai-agents \
  --add-topic autonomous-agents \
  --add-topic fastapi \
  --add-topic react \
  --add-topic vite \
  --add-topic multi-tenant \
  --add-topic llm \
  --add-topic ollama
```
