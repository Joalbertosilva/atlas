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
    first = rows[0]
    assert first.get("sq_candidato")
    assert first.get("cd_eleicao")
    assert first.get("sg_ue")
    kinds = client.get("/api/results/ranking?cargo=1&turno=1&kind=todas").json["data"]
    special = {k["kind"] for k in kinds}
    assert "branco" in special and "nulo" in special
    by_nr = {row["nr_votavel"]: row for row in rows}
    if "22" in by_nr:
        assert by_nr["22"]["sg_partido"] == "PL"
        assert by_nr["22"]["color"].upper() == "#F5C400"
    if "13" in by_nr:
        assert by_nr["13"]["sg_partido"] == "PT"
        assert by_nr["13"]["color"].upper() == "#E30613"


def test_governor_uf_leaders_national_overview(client):
    r = client.get("/api/results/uf-leaders?cargo=3&turno=1&ano=2026")
    if r.status_code == 404:
        pytest.skip("governador 2026 ainda não publicado")
    assert r.status_code == 200
    rows = r.json["data"]
    ufs = {row["sg_uf"] for row in rows}
    assert "ZZ" not in ufs
    winners = [row for row in rows if row.get("leader")]
    assert winners
    assert all(row["leader"]["color"] for row in winners)
    assert all(row["leader"].get("sq_candidato") for row in winners)


def test_2022_official_photo_from_tse_zip(client):
    r = client.get("/api/photos/2022/BR/280001607829")
    if r.status_code in (404, 503):
        pytest.skip("ZIP de fotos 2022 indisponível neste ambiente")
    assert r.status_code == 200
    assert r.mimetype.startswith("image/")
    assert r.data[:3] == b"\xff\xd8\xff"


def test_presidential_uf_leaders_for_map(client):
    r = client.get("/api/results/municipalities?cargo=1&turno=1&mode=leader&level=uf")
    if r.status_code == 404:
        pytest.skip("ranking presidencial ainda não publicado")
    assert r.status_code == 200
    rows = r.json["data"]
    ufs = {row["sg_uf"] for row in rows}
    assert "ZZ" not in ufs
    assert len(ufs) >= 27
    with_leader = [row for row in rows if row.get("leader")]
    assert with_leader
    assert all(row["leader"]["color"] for row in with_leader)
    assert all(not row.get("cd_municipio_ibge") for row in rows)
    assert all(row["leader"]["qt_votos_validos"] > 0 for row in with_leader)


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


def test_poll_stats_splits_second_round_window(client):
    r = client.get("/api/search/polls/stats?cargo=Presidente&janela=2")
    if r.status_code == 404:
        pytest.skip("pesquisas ainda não publicadas")
    assert r.status_code == 200
    data = r.json["data"]
    assert data["janela"] == "2"
    assert data["dt_primeiro_turno"]
    assert data["dt_segundo_turno"]
    assert data["total"] >= 0
    assert "por_mes" in data
    notes = " ".join(r.json["meta"]["notes"])
    assert "percentuais" in notes
    listed = client.get("/api/search/polls?cargo=Presidente&janela=2&page_size=5")
    assert listed.status_code == 200
    assert listed.json["meta"]["pagination"]["total"] == data["total"]


def test_poll_ficha_abre_e_leitura_traz_urna(client):
    listed = client.get("/api/search/polls?cargo=Presidente&janela=2&page_size=1")
    if listed.status_code != 200 or not listed.json.get("data"):
        pytest.skip("pesquisas do 2º turno ainda não publicadas")
    proto = listed.json["data"][0]["nr_protocolo_registro"]
    ficha = client.get(f"/api/search/polls/{proto}")
    assert ficha.status_code == 200
    assert ficha.json["data"]["nr_protocolo_registro"] == proto
    assert "ds_metodologia_pesquisa" in ficha.json["data"]
    leitura = client.post(f"/api/search/polls/{proto}/leitura", json={"cargo": "1"})
    assert leitura.status_code == 200
    body = leitura.json["data"]
    assert body["poll"]["nr_protocolo_registro"] == proto
    nrs = {row["nr_votavel"] for row in body["urna"]}
    assert "13" in nrs and "22" in nrs
    assert "hits" in body and "mencoes" in body
    assert body["janela"] in ("1", "2", "todas")


def test_poll_inexistente_404(client):
    r = client.get("/api/search/polls/BR999999026")
    assert r.status_code == 404


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


def test_party_compare_2026_real_2022_status(client):
    r = client.get("/api/results/party-compare?cargo=1&turno=1&metrica=nominais")
    if r.status_code == 404:
        pytest.skip("Presidência 2026 ainda não publicada")
    assert r.status_code == 200
    body = r.json
    assert body["data"]["years"]["2026"]["available"] is True
    y22 = body["data"]["years"]["2022"]
    assert body["data"]["parties"]
    first = body["data"]["parties"][0]
    assert first["votos_2026"] is not None
    assert "qt_total_votos_validos" in body["meta"]["denominators"]["pct"]
    if y22["available"]:
        assert y22["total_validos"]
        assert y22["ano"] == 2022
    else:
        assert y22["total_validos"] is None
        assert first["votos_2022"] is None
        assert first["variacao_relativa"] == "indisponivel"
        assert any("2022" in n for n in body["meta"]["coverage"]["notes"])


def test_ranking_accepts_ano_and_cross_compare_schema(client):
    r = client.get("/api/results/ranking?cargo=1&turno=1&ano=2026")
    if r.status_code == 404:
        pytest.skip("ranking presidencial ainda não publicado")
    rows = r.json["data"]
    assert rows
    missing = client.get("/api/results/ranking?cargo=1&turno=1&ano=2022")
    if missing.status_code == 404:
        return
    a = rows[0]["option_id"]
    b = missing.json["data"][0]["option_id"]
    cmp = client.get(f"/api/results/cross-compare?cargo=1&turno=1&option_ids={a},{b}")
    assert cmp.status_code == 200
    data = cmp.json["data"]
    assert len(data["options"]) == 2
    assert {o["ano"] for o in data["options"]} <= {2022, 2026}
    assert "delta_pp" in data["places"][0]
