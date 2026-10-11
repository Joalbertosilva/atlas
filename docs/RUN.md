# Como ligar o Atlas no dia a dia

Três processos. O site só aparece se os três existirem (ou ser equivalentes).

## 1. Banco + busca + API (Docker)

Uma vez por sessão, ou depois de reiniciar o notebook:

```fish
cd /home/joao/Documentos/eleicao2026
source .venv/bin/activate.fish
docker compose up -d db searxng api
curl -sS http://127.0.0.1:8070/api/health
```

Tem que voltar `"status":"ok"`. Isso **não** abre o mapa no browser — só o backend.

## 2. Front (`npm run dev` basta)

Se o passo 1 já estiver no ar:

```fish
cd /home/joao/Documentos/eleicao2026
npm --prefix frontend run dev
```

Abra **http://127.0.0.1:5173/**

Não precisa de Docker de novo para o React. O Vite só encaminha `/api` para a porta `8070`. Sem o passo 1, a tela abre vazia.

## 3. Carga que ainda falta (uma vez)

```fish
cd /home/joao/Documentos/eleicao2026
source .venv/bin/activate.fish
./scripts/finish_secao.sh
```

Importa seção de SP e ZZ e roda o `reconcile`. SP é lento. Não rode se outro `atlas-etl` estiver ativo.
