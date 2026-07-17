#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-agents_morf}" "${POSTGRES_DB:-agents_morf}" | gzip > "backups/postgres-${stamp}.sql.gz"
echo "Backup written to backups/postgres-${stamp}.sql.gz"
