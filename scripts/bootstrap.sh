#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env. Edit all CHANGE_ME values before production."
fi

docker compose up -d --build
docker compose ps

echo "Next: create an administrator with:"
echo "docker compose exec backend python -m app.cli create-admin --email admin@example.com --password 'CHANGE_THIS' --organization CodeMorf"
