#!/bin/sh
# Rode no MESMO terminal em que o curl da API funcionou, depois de
# `tail data/logs/import_secao.log` mostrar FIM — ou se o loop original já acabou.
# Não inicia segundo ETL se ainda houver import de seção.
set -eu
cd "$(dirname "$0")/.."
# Só o binário de verdade. `pgrep -f 'atlas-etl import secao'` pega lixo de terminal
# (comandos antigos do Cursor cujo texto contém essa frase).
if pgrep -f '.venv/bin/atlas-etl import secao' >/dev/null 2>&1; then
  echo "ainda há import de seção de verdade; espere acabar" >&2
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
atlas-etl import secao --ue SP
atlas-etl import secao --ue ZZ
atlas-etl reconcile --show 40
atlas-etl coverage -v
