# Deployment

Target: Ubuntu 24.04 behind aaPanel Nginx and Cloudflare.

## 1. Clone

```bash
cd /opt
git clone https://github.com/CodeMorf/agents-Morf.git
cd agents-Morf
cp .env.example .env
nano .env
```

Generate secure values:

```bash
openssl rand -hex 32
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 2. Start

Without local Ollama:

```bash
docker compose up -d --build
```

With local Ollama:

```bash
docker compose --profile local-ai up -d --build
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull nomic-embed-text
```

## 3. Create administrator

```bash
docker compose exec backend python -m app.cli create-admin \
  --email admin@codemorf.tech \
  --password 'LONG_UNIQUE_PASSWORD' \
  --organization CodeMorf
```

## 4. Reverse proxy

The included Nginx container listens on port 80. In aaPanel you can either proxy `agent.codemorf.tech` to the Compose Nginx service or adapt `infrastructure/nginx/default.conf` to the host Nginx.

Required behavior:

- `/` serves the React build;
- `/api/` proxies to FastAPI;
- proxy buffering is disabled for streaming;
- `/api/*` is never cached;
- static hashed assets may be cached for one year.

## 5. Cloudflare

- DNS record `agent` points to the VPS.
- Origin certificate installed.
- SSL/TLS mode: **Full (strict)**.
- Always Use HTTPS: enabled.
- Cache bypass for `/api/*` and authenticated HTML.
- Rate limiting can be added after baseline traffic is measured.

## 6. Health

```bash
curl http://127.0.0.1/api/v1/health
curl http://127.0.0.1/api/v1/ready
```

## Updating

```bash
git pull --ff-only
docker compose up -d --build
docker compose ps
```

Back up PostgreSQL and persistent volumes before schema-changing releases.
