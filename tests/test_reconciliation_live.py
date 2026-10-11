"""Totais nacionais conferidos contra os arquivos TSE lidos em 2026-10-11.

Fonte: votacao_candidato_munzona_2026_BR.csv e detalhe_votacao_munzona_2026_BR.csv
(eleição 6257, cargo 1, 1º turno). Não usa dados de outro ano.
"""
import pytest


PRESIDENTE_VALIDOS = {
    "22": 56_104_503,  # FLAVIO BOLSONARO
    "13": 53_879_538,  # LULA
}
COMPARECIMENTO_BR = 125_275_835
VALIDOS_BR = 119_300_788
APTOS_BR = 158_745_502
ZZ_COMPARECIMENTO = 341_766


@pytest.mark.integration
def test_presidente_totais_nacionais(database_url):
    import psycopg
    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT o.nr_votavel, sum(r.qt_votos_validos)
            FROM agg.result_state r
            JOIN core.vote_option o ON o.id = r.option_id
            JOIN core.contest c ON c.id = r.contest_id
            WHERE c.cd_cargo = '1' AND c.nr_turno = 1 AND o.kind = 'candidatura'
            GROUP BY 1""")
        got = {nr: int(v) for nr, v in cur.fetchall()}
        if not got:
            pytest.skip("agregados presidenciais ainda não reconstruídos")
        for nr, exp in PRESIDENTE_VALIDOS.items():
            assert got.get(nr) == exp, f"candidato {nr}: {got.get(nr)} != {exp}"
        cur.execute("""
            SELECT sum(qt_comparecimento), sum(qt_aptos), sum(qt_total_votos_validos)
            FROM agg.turnout_state t JOIN core.contest c ON c.id = t.contest_id
            WHERE c.cd_cargo = '1' AND c.nr_turno = 1""")
        comp, aptos, validos = cur.fetchone()
        assert int(comp) == COMPARECIMENTO_BR
        assert int(aptos) == APTOS_BR
        assert int(validos) == VALIDOS_BR
        cur.execute("""
            SELECT sum(qt_comparecimento) FROM agg.turnout_state t
            JOIN core.contest c ON c.id = t.contest_id
            WHERE c.cd_cargo = '1' AND c.nr_turno = 1 AND t.sg_uf = 'ZZ'""")
        zz = cur.fetchone()[0]
        if zz is not None:
            assert int(zz) == ZZ_COMPARECIMENTO
            assert int(zz) < int(comp)
