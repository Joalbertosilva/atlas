#!/bin/sh
# Sobe db + searxng + api sem apagar volumes. Rode no host com Docker.
set -eu
cd "$(dirname "$0")/.."
docker compose up -d db searxng
docker compose up -d --force-recreate --no-deps api
docker compose ps
echo "health:"
curl -sS http://127.0.0.1:8070/api/health || true
echo
echo "depois: npm --prefix frontend run dev   e/ou  ./scripts/resume_load.sh"
