"""Contrato da API contra o banco local (dados reais já publicados) ou skip."""
import os

import pytest

from atlas_api import create_app
from atlas_api.config import Config


@pytest.fixture
def client(database_url, cache_secret):
    import httpx

    class Transport(httpx.BaseTransport):
        def handle_request(self, request):
            if request.url.path.endswith("/healthz"):
                return httpx.Response(200, text="ok")
            return httpx.Response(200, json={"results": [], "unresponsive_engines": []})

    cfg = Config(
        database_url=database_url if "+psycopg" in database_url else database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1),
        searxng_url="http://searxng:8080",
        search_timeout=2,
        search_cache_ttl=60,
        search_rate_limit=50,
        cache_secret=cache_secret,
        cors_origins=[],
    )
    app = create_app(cfg, search_transport=Transport())
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json["data"]["database"] == "ok"


def test_offices_and_states(client):
    offices = client.get("/api/offices").json["data"]
    codes = {o["cd_cargo"] for o in offices}
    assert codes == {"1", "3", "5", "6", "7", "8"}
    states = client.get("/api/states").json["data"]
    ufs = {s["sg_uf"] for s in states}
    assert "AC" in ufs and "ZZ" in ufs
    assert any(s["is_exterior"] for s in states if s["sg_uf"] == "ZZ")


def test_presidential_ranking_has_denominators(client):
    r = client.get("/api/results/ranking?cargo=1&turno=1")
    if r.status_code == 404:
        pytest.skip("ranking presidencial ainda não publicado")
    body = r.json
    assert body["meta"]["denominators"]["pct_validos"]
    rows = body["data"]
    assert rows
    assert all(row["kind"] == "candidatura" for row in rows)
    assert "ds_sit_tot_turno" in rows[0]
    kinds = client.get("/api/results/ranking?cargo=1&turno=1&kind=todas").json["data"]
    special = {k["kind"] for k in kinds}
    assert "branco" in special and "nulo" in special


def test_summary_exterior_separated(client):
    r = client.get("/api/results/summary?cargo=1&turno=1")
    if r.status_code == 404:
        pytest.skip("summary ainda não publicado")
    data = r.json["data"]
    assert "qt_aptos" in data
    assert data["choices_per_voter"] == 1
    # Exterior é campo separado; totais nacionais já o incluem na fonte munzona BR.
    if data["exterior"]:
        assert data["exterior"]["qt_comparecimento"] <= data["qt_comparecimento"]


def test_senator_warning(client):
    r = client.get("/api/results/ranking?cargo=5&turno=1&uf=AC")
    if r.status_code == 404:
        pytest.skip("Acre ainda não publicado")
    notes = " ".join(r.json["meta"]["coverage"]["notes"])
    assert "2" in notes and "Senador" in notes


def test_search_post_does_not_require_query_string(client):
    r = client.post("/api/search/web", json={"q": "TSE 2026"})
    assert r.status_code == 200
    assert "data" in r.json
    assert r.json["meta"]["query_sent"]


def test_invalid_cargo(client):
    r = client.get("/api/results/summary?cargo=99")
    assert r.status_code in (400, 422)


def test_openapi_published(client):
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    assert "/api/results/ranking" in r.get_data(as_text=True)
