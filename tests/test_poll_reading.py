from atlas_api.search.poll_reading import (
    cargos_from_ds,
    coverage_query,
    extract_mentions,
    is_second_round_coverage,
    pick_cargo,
    runoff_candidates,
)


CANDS = [
    {"option_id": 1, "label": "FLAVIO BOLSONARO", "nr_votavel": "22", "sg_partido": "PL", "color": "#F5C400"},
    {"option_id": 2, "label": "LULA", "nr_votavel": "13", "sg_partido": "PT", "color": "#E30613"},
]


def test_extracts_percentages_next_to_official_names():
    text = "Pesquisa Datafolha: Lula 45,2% e Flávio Bolsonaro 47% dos votos válidos."
    out = {m["label"]: m["pct_mencao"] for m in extract_mentions(text, CANDS)}
    assert out["LULA"] == 45.2
    assert out["FLAVIO BOLSONARO"] == 47.0


def test_extracts_last_name_next_to_percent():
    text = "Bolsonaro aparece com 46,8% e Lula com 44,1%."
    out = {m["label"]: m["pct_mencao"] for m in extract_mentions(text, CANDS)}
    assert out["FLAVIO BOLSONARO"] == 46.8
    assert out["LULA"] == 44.1


def test_does_not_invent_or_use_year_as_percent():
    text = "Instituto Verita registrou a pesquisa em 2026 com 2002 entrevistados."
    assert extract_mentions(text, CANDS) == []


def test_requires_percent_sign():
    text = "Lula 45 Flávio 47 sem o símbolo."
    assert extract_mentions(text, CANDS) == []


def test_cargo_from_poll_description():
    assert cargos_from_ds("Presidente") == ["1"]
    assert pick_cargo("Governador, Senador", "5") == "5"
    assert pick_cargo("Governador, Senador", "1") == "3"


def test_second_round_coverage_requires_round_words():
    assert is_second_round_coverage("Pesquisa do 2º turno: Lula 52%")
    assert is_second_round_coverage("CNT/MDA no segundo turno")
    assert not is_second_round_coverage("CNT/MDA na véspera do 1º turno: Lula 47,8%")


def test_runoff_filters_official_status():
    rows = [
        {"label": "FLAVIO BOLSONARO", "ds_sit_tot_turno": "2º TURNO"},
        {"label": "LULA", "ds_sit_tot_turno": "2º TURNO"},
        {"label": "ZEMA", "ds_sit_tot_turno": "NÃO ELEITO"},
    ]
    assert [r["label"] for r in runoff_candidates(rows)] == ["FLAVIO BOLSONARO", "LULA"]


def test_coverage_query_uses_protocol_and_institute():
    q = coverage_query({
        "nm_empresa_fantasia": "DATAVERO",
        "nm_empresa": "DATAVERO PESQUISA",
        "ds_cargo": "Presidente",
        "sg_uf": "BR",
        "nr_protocolo_registro": "BR023672026",
    })
    assert "DATAVERO" in q and "BR023672026" in q and "Presidente" in q
