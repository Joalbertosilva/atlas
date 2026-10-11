#!/bin/sh
# Retoma só o que falta (hoje: secao:*). Não apaga volumes. Não rode se já
# existir outro atlas-etl. ZIPs de seção já estão em data/downloads/secao/.
set -eu
cd "$(dirname "$0")/.."
if pgrep -f 'atlas-etl (resume|import)' >/dev/null 2>&1; then
  echo "já existe atlas-etl em execução — não iniciar um segundo" >&2
  exit 1
fi
. ./.venv/bin/activate
set -a
. ./.env
set +a
# dash (/bin/sh) não aceita ${var/a/b}; sed é POSIX
DATABASE_URL=$(printf '%s' "$DATABASE_URL" | sed 's/@db:5432/@127.0.0.1:55432/')
export DATABASE_URL
export ATLAS_DOWNLOAD_DIR="${ATLAS_DOWNLOAD_DIR:-$PWD/data/downloads}"

echo "== cobertura antes =="
atlas-etl coverage -v

echo "== retomar recortes não publicados (secao) =="
atlas-etl resume

echo "== reconciliação =="
atlas-etl reconcile --show 40
atlas-etl coverage -v
