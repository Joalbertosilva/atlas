"""Busca com transporte HTTP sintético (não é consulta real ao SearXNG)."""
import httpx
from sqlalchemy import create_engine, text

from atlas_api.search.service import SearchService


class _FakeTransport(httpx.BaseTransport):
    def __init__(self, payload: dict, status: int = 200):
        self.payload = payload
        self.status = status
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(self.status, json=self.payload)


def _svc(payload, engine, status=200):
    t = _FakeTransport(payload, status)
    return SearchService("http://searxng:8080", 2, 60, b"secret", engine, 20, transport=t), t


def test_normalize_dedupes_sanitizes_and_skips_bad_urls(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/c.db")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE search_cache (cache_key text, mode text, payload text, created_at text, expires_at text)"))
    raw = {
        "results": [
            {"title": "<b>TSE</b>", "url": "https://www.tse.jus.br/a?utm_source=x",
             "content": "<script>x</script>trecho", "engines": ["bing"], "publishedDate": "2026-10-04T12:00:00"},
            {"title": "dup", "url": "https://tse.jus.br/a", "content": "y", "engines": ["duckduckgo"]},
            {"title": "js", "url": "javascript:alert(1)", "content": "z", "engines": ["bing"]},
        ],
        "unresponsive_engines": [["mojeek", "access denied"]],
    }
    svc, _ = _svc(raw, engine)
    data, meta = svc.search("news", "eleicoes 2026", 1)
    assert len(data) == 1
    assert data[0]["title"] == "TSE"
    assert "<script>" not in data[0]["snippet"]
    assert data[0]["published_at"] == "2026-10-04T12:00:00"
    assert meta["status"] == "parcial"
    engines = {p["engine"]: p for p in meta["providers"]}
    assert engines["mojeek"]["status"] == "indisponivel"
    assert engines["bing"]["status"] == "ok"


def test_empty_news_falls_back_to_web():
    class Seq(httpx.BaseTransport):
        def __init__(self):
            self.calls = 0

        def handle_request(self, request):
            self.calls += 1
            if "categories=news" in str(request.url):
                return httpx.Response(200, json={"results": [], "unresponsive_engines": [["bing news", "parsing error"]]})
            return httpx.Response(200, json={"results": [
                {"title": "TSE", "url": "https://www.tse.jus.br/n", "content": "oficial", "engines": ["duckduckgo"]},
            ], "unresponsive_engines": []})

    engine = create_engine("sqlite://")
    t = Seq()
    svc = SearchService("http://searxng:8080", 2, 60, b"s", engine, 20, transport=t)
    data, meta = svc.search("news", "lula", 1)
    assert len(data) == 1
    assert data[0]["url"].startswith("https://www.tse.jus.br")
    assert meta["fallback"] == "web"
    assert meta["status"] == "parcial"
    assert t.calls == 2


def test_timeout_is_unavailable_not_fake_results():
    class Boom(httpx.BaseTransport):
        def handle_request(self, request):
            raise httpx.TimeoutException("t")

    engine = create_engine("sqlite://")
    svc = SearchService("http://searxng:8080", 1, 60, b"s", engine, 20, transport=Boom())
    data, meta = svc.search("web", "teste", 1)
    assert data == []
    assert meta["status"] == "indisponivel"
    assert meta["cache"]["ttl_seconds"] == 0


def test_fact_checks_only_keep_listed_publishers():
    engine = create_engine("sqlite://")
    raw = {"results": [
        {"title": "checagem", "url": "https://g1.globo.com/fato-ou-fake/x", "content": "a", "engines": ["bing"]},
        {"title": "noticia", "url": "https://g1.globo.com/politica/x", "content": "b", "engines": ["bing"]},
    ], "unresponsive_engines": []}
    svc, _ = _svc(raw, engine)
    data, meta = svc.search("fact-checks", "alegacao", 1)
    assert len(data) == 1
    assert data[0]["status"] == "checagem_publicada_identificada"
    assert data[0]["rating"] is None
    assert meta["status"] == "ok"


def test_rate_limiter_blocks_after_limit():
    from atlas_api.search.service import RateLimiter
    lim = RateLimiter(2, b"s")
    assert lim.allow("1.1.1.1")[0]
    assert lim.allow("1.1.1.1")[0]
    ok, retry = lim.allow("1.1.1.1")
    assert ok is False
    assert retry >= 1
