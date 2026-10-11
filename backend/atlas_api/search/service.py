"""Cliente do SearXNG próprio (rede interna do Compose) + cache HMAC + rate limit.

Somente o backend fala com o SearXNG; o navegador nunca recebe a URL nem o segredo dele.
Nenhum mecanismo bloqueado é contornado: CAPTCHA/429/acesso negado aparecem como
"indisponivel" no status do provedor e o resultado é apresentado como parcial.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from collections import deque
from datetime import datetime, timezone

import httpx
from sqlalchemy import text

from . import factcheck
from .sanitize import clean_text, dedupe_key, domain_of, parse_date, safe_url

CATEGORY = {"web": "general", "news": "news", "fact-checks": "general"}
MAX_RESULTS = 30


class RateLimiter:
    """Janela deslizante em memória. A chave é um hash do IP (com segredo), nunca persistido."""

    def __init__(self, per_minute: int, secret: bytes):
        self.per_minute = per_minute
        self.secret = secret
        self.hits: dict[str, deque] = {}
        self.lock = threading.Lock()

    def allow(self, ip: str) -> tuple[bool, int]:
        key = hmac.new(self.secret, ip.encode(), hashlib.sha256).hexdigest()[:24]
        now = time.monotonic()
        with self.lock:
            q = self.hits.setdefault(key, deque())
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False, int(60 - (now - q[0])) + 1
            q.append(now)
            if len(self.hits) > 10000:  # limpeza de chaves ociosas
                for k in [k for k, v in self.hits.items() if not v or now - v[-1] > 60]:
                    del self.hits[k]
            return True, 0


class SearchService:
    def __init__(self, base_url: str, timeout: float, ttl: int, secret: bytes, write_engine, rate_per_minute: int,
                 transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.ttl = ttl
        self.secret = secret
        self.engine = write_engine
        self.limiter = RateLimiter(rate_per_minute, self.secret)
        self.engine_state: dict[str, dict] = {}  # último resultado observado por mecanismo (em memória)
        self.client = httpx.Client(timeout=httpx.Timeout(timeout, connect=min(3.0, timeout)), transport=transport,
                                   follow_redirects=False, headers={"Accept": "application/json"})

    # ---------------------------------------------------------------- consulta
    @staticmethod
    def build_query(q: str, uf: str | None, municipio_nome: str | None, candidato: str | None, mode: str) -> str:
        parts = [" ".join(q.split())]
        for extra in (candidato, municipio_nome, uf):
            if extra and extra.lower() not in parts[0].lower():
                parts.append(extra)
        if mode == "fact-checks":
            parts.append("checagem")
        return " ".join(parts)[:300]

    def cache_key(self, mode: str, query: str, page: int) -> str:
        return hmac.new(self.secret, f"{mode}\x00{page}\x00{query.lower()}".encode(), hashlib.sha256).hexdigest()

    def _cache_get(self, key: str):
        with self.engine.begin() as c:
            row = c.execute(text("SELECT payload, created_at FROM app.search_cache WHERE cache_key = :k AND expires_at > now()"),
                            {"k": key}).first()
        return row

    def _cache_put(self, key: str, mode: str, payload: dict) -> None:
        with self.engine.begin() as c:
            c.execute(text("DELETE FROM app.search_cache WHERE expires_at <= now()"))
            c.execute(text("""INSERT INTO app.search_cache (cache_key, mode, payload, expires_at)
                              VALUES (:k, :m, CAST(:p AS jsonb), now() + make_interval(secs => :ttl))
                              ON CONFLICT (cache_key) DO UPDATE SET payload = EXCLUDED.payload,
                                  created_at = now(), expires_at = EXCLUDED.expires_at"""),
                      {"k": key, "m": mode, "p": json.dumps(payload), "ttl": self.ttl})

    def _fetch(self, query: str, category: str, page: int) -> dict:
        r = self.client.get(f"{self.base_url}/search", params={
            "q": query, "format": "json", "language": "pt-BR", "categories": category, "pageno": page,
            "safesearch": 1})
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _providers(raw: dict) -> list[dict]:
        counts: dict[str, int] = {}
        for item in raw.get("results") or []:
            for e in item.get("engines") or [item.get("engine")]:
                if isinstance(e, str):
                    counts[e] = counts.get(e, 0) + 1
        prov = [{"engine": e, "status": "ok", "reason": None, "results": n} for e, n in sorted(counts.items())]
        for entry in raw.get("unresponsive_engines") or []:
            if isinstance(entry, (list, tuple)) and entry:
                prov.append({"engine": clean_text(entry[0], 40), "status": "indisponivel",
                             "reason": clean_text(entry[1] if len(entry) > 1 else "", 120) or None, "results": 0})
        return prov

    @staticmethod
    def _normalize(raw: dict) -> list[dict]:
        out, seen = [], set()
        for item in raw.get("results") or []:
            url = safe_url(item.get("url"))
            if not url:
                continue
            k = dedupe_key(url)
            if k in seen:
                continue
            seen.add(k)
            engines = [clean_text(e, 40) for e in (item.get("engines") or [item.get("engine")]) if isinstance(e, str)]
            out.append({"title": clean_text(item.get("title"), 300) or domain_of(url), "url": url,
                        "domain": domain_of(url), "snippet": clean_text(item.get("content"), 500),
                        "engines": engines, "published_at": parse_date(item.get("publishedDate"))})
            if len(out) >= MAX_RESULTS:
                break
        return out

    def search(self, mode: str, query: str, page: int) -> tuple[list[dict], dict]:
        category = CATEGORY[mode]
        key = self.cache_key(mode, query, page)
        try:
            hit = self._cache_get(key)
        except Exception:  # noqa: BLE001 - cache indisponível não impede a busca
            hit = None
        if hit is not None:
            payload, created = hit
            meta = dict(payload["meta"], cache={"hit": True, "fetched_at": created.isoformat(), "ttl_seconds": self.ttl})
            return payload["data"], meta
        fetched_at = datetime.now(timezone.utc).isoformat()
        try:
            raw = self._fetch(query, category, page)
        except (httpx.HTTPError, ValueError) as exc:
            reason = "tempo esgotado" if isinstance(exc, httpx.TimeoutException) else "SearXNG indisponível"
            return [], {"query_sent": query, "category": category, "providers": [], "status": "indisponivel",
                        "reason": reason, "cache": {"hit": False, "fetched_at": fetched_at, "ttl_seconds": 0}}
        data = self._normalize(raw)
        providers = self._providers(raw)
        fallback = None
        if mode == "news" and not data:
            try:
                raw_web = self._fetch(query, "general", page)
            except (httpx.HTTPError, ValueError):
                raw_web = None
            if raw_web:
                extra = self._normalize(raw_web)
                providers = providers + self._providers(raw_web)
                if extra:
                    data = extra
                    fallback = "web"
        now = datetime.now(timezone.utc).isoformat()
        for p in providers:
            self.engine_state[p["engine"]] = {"status": p["status"], "reason": p["reason"], "at": now}
        if mode == "fact-checks":
            data = self._fact_checks(data)
        failed = any(p["status"] != "ok" for p in providers)
        if mode == "fact-checks":
            status = "ok" if data else ("fonte_temporariamente_indisponivel" if failed and not
                                        any(p["status"] == "ok" for p in providers) else "sem_correspondencia_suficiente")
        else:
            status = "indisponivel" if not data and failed else ("parcial" if failed or fallback else "ok")
        meta = {"query_sent": query, "category": category, "providers": providers, "status": status}
        if fallback:
            meta["fallback"] = fallback
        if mode == "fact-checks":
            meta["allowed_publishers"] = factcheck.allowed_publishers()
        if status not in ("indisponivel", "fonte_temporariamente_indisponivel"):
            try:
                self._cache_put(key, mode, {"data": data, "meta": meta})
            except Exception:  # noqa: BLE001
                pass
        meta["cache"] = {"hit": False, "fetched_at": fetched_at, "ttl_seconds": self.ttl}
        return data, meta

    @staticmethod
    def _fact_checks(results: list[dict]) -> list[dict]:
        out = []
        for r in results:
            m = factcheck.match(r["url"])
            if not m:
                continue
            pub, is_check = m
            out.append({**r, "publisher": pub.name, "rating": None,
                        "status": "checagem_publicada_identificada" if is_check else "possivel_checagem_relacionada"})
        return out

    # ------------------------------------------------------------------ status
    def ping(self) -> bool:
        try:
            return self.client.get(f"{self.base_url}/healthz", timeout=2.0).status_code == 200
        except httpx.HTTPError:
            return False

    def status(self) -> dict:
        try:
            r = self.client.get(f"{self.base_url}/config", timeout=3.0)
            r.raise_for_status()
            cfg = r.json()
        except (httpx.HTTPError, ValueError):
            return {"searxng": "indisponivel", "version": None, "engines": []}
        engines = []
        for e in cfg.get("engines") or []:
            if not e.get("enabled", True):
                continue
            name = clean_text(e.get("name"), 40)
            seen = self.engine_state.get(name)
            engines.append({"name": name,
                            "category": ",".join(c for c in (e.get("categories") or []) if isinstance(c, str))[:80],
                            "status": seen["status"] if seen else "sem_uso_recente",
                            "last_error": seen["reason"] if seen and seen["status"] != "ok" else None,
                            "observed_at": seen["at"] if seen else None})
        return {"searxng": "ok", "version": clean_text(cfg.get("version"), 40) or None, "engines": engines}
