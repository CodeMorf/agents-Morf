# Production deployment

## 1. Server

Recommended baseline: Ubuntu 24.04, Docker Engine, Docker Compose plugin and at least 8 GB RAM. Local LLM requirements depend on model size and usually need considerably more RAM or a GPU.

## 2. DNS

Create an `A` record:

```text
agent.codemorf.tech → SERVER_IP
```

Use DNS-only while installing the origin certificate, then enable the Cloudflare proxy.

## 3. Configure

```bash
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

Set `SECRET_KEY`, `ENCRYPTION_KEY`, database password and only the provider keys in use.

## 4. Start

```bash
docker compose up -d --build
docker compose ps
```

Create the first administrator:

```bash
docker compose exec backend python -m app.cli create-admin \
  --email admin@codemorf.tech \
  --password 'USE_A_UNIQUE_LONG_PASSWORD' \
  --organization CodeMorf
```

## 5. aaPanel / Nginx

This repository includes a containerized Nginx. If aaPanel owns ports 80/443, either:

- let aaPanel proxy `agent.codemorf.tech` to the container on a different port, or
- stop aaPanel's site-level Nginx and use this stack's Nginx.

Do not have two services binding the same port.

## 6. Cloudflare

- SSL/TLS: Full (strict)
- Always Use HTTPS: enabled
- Proxy: enabled after origin TLS works
- Cache bypass for `/api/*`
- Cache static hashed assets under `/assets/*`
- Never cache authenticated responses

## 7. Updates

```bash
git pull --ff-only
docker compose up -d --build
docker image prune -f
```
