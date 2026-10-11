"""Idempotência e manifesto — usa arquivos reais baixados quando existirem."""
from pathlib import Path

import pytest
import yaml

from atlas_etl.manifest import load_manifest
from atlas_etl.runs import published_fingerprint
from atlas_etl.zipsafe import list_members

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_only_official_hosts():
    resources = load_manifest(ROOT / "data/manifests/tse_2026.yaml")
    assert resources
    for r in resources:
        assert r.url.startswith(("https://cdn.tse.jus.br/", "https://servicodados.ibge.gov.br/"))
        assert "2022" not in r.url or r.kind.startswith("ibge")
        if r.kind != "ibge_malha_municipio" and r.kind != "ibge_malha_uf":
            assert "2026" in r.url or r.key == "municipio_tse_ibge"


def test_manifest_does_not_claim_catalog_for_cdn_only_results():
    doc = yaml.safe_load((ROOT / "data/manifests/tse_2026.yaml").read_text())
    by_key = {r["key"]: r for r in doc["resources"]}
    assert by_key["votacao_candidato_munzona_2026"]["listed_in_catalog"] is False
    assert by_key["consulta_cand_2026"]["listed_in_catalog"] is True


@pytest.mark.integration
def test_same_fingerprint_is_skipped(database_url):
    import psycopg
    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    zpath = ROOT / "data/downloads/consulta_vagas_2026.zip"
    if not zpath.exists():
        pytest.skip("arquivo de vagas não baixado")
    members = list_members(zpath)
    br = next(m for m in members if m.name.endswith("_BRASIL.csv"))
    fp = f"{br.name}:{br.crc32}:{br.size}"
    try:
        conn = psycopg.connect(url)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL do Atlas indisponível neste ambiente")
    with conn:
        pub = published_fingerprint(conn, "ref:consulta_vagas")
    if pub is None:
        pytest.skip("vagas ainda não publicadas")
    assert pub == fp


def test_no_paid_api_keys_in_example_env():
    text = (ROOT / ".env.example").read_text()
    for needle in ("GOOGLE_API", "SERPAPI", "BRAVE_API", "OPENAI", "sk-"):
        assert needle not in text
    compose = (ROOT / "compose.yaml").read_text()
    assert "kafka" not in compose.lower()
    assert "airflow" not in compose.lower()
