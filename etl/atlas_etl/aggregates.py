"""Reconstrução transacional dos agregados a partir de fact.*_munzona (grão oficial de totalização).

Os agregados NÃO usam fact.vote_section: seção e munzona representam os mesmos votos e
somá-los duplicaria a contagem. A seção é usada apenas na navegação e na reconciliação.
"""
import logging
import time

import psycopg

log = logging.getLogger(__name__)

TURNOUT_SUMS = """sum(qt_aptos), sum(qt_comparecimento), sum(qt_abstencoes), sum(qt_votos),
    sum(qt_total_votos_validos), sum(qt_votos_nominais_validos), sum(qt_total_votos_leg_validos),
    sum(qt_votos_brancos), sum(qt_total_votos_nulos), sum(qt_total_votos_anul_subjud),
    sum(qt_total_votos_anulados), sum(qt_total_secoes), max(dt_ultima_totalizacao),
    sum(qt_eleitores_secoes_nao_instaladas)"""


def rebuild(conn: psycopg.Connection) -> dict:
    t0 = time.time()
    with conn.cursor() as cur:
        cur.execute("SET LOCAL work_mem = '256MB'")
        cur.execute("TRUNCATE agg.result_municipality, agg.result_state, agg.turnout_municipality, agg.turnout_state")
        cur.execute("""
            INSERT INTO agg.result_municipality (contest_id, cd_municipio_tse, sg_uf, option_id, qt_votos, qt_votos_validos)
            SELECT contest_id, cd_municipio_tse, sg_uf, option_id, sum(qt_votos), sum(qt_votos_validos)
            FROM fact.vote_munzona GROUP BY 1, 2, 3, 4""")
        n_mun = cur.rowcount
        cur.execute("""
            INSERT INTO agg.result_state (contest_id, sg_uf, option_id, qt_votos, qt_votos_validos)
            SELECT contest_id, sg_uf, option_id, sum(qt_votos), sum(qt_votos_validos)
            FROM agg.result_municipality GROUP BY 1, 2, 3""")
        n_uf = cur.rowcount
        cur.execute(f"""
            INSERT INTO agg.turnout_municipality
            SELECT contest_id, cd_municipio_tse, sg_uf, {TURNOUT_SUMS}
            FROM fact.turnout_munzona GROUP BY 1, 2, 3""")
        cur.execute(f"""
            INSERT INTO agg.turnout_state
            SELECT contest_id, sg_uf, {TURNOUT_SUMS}
            FROM fact.turnout_munzona GROUP BY 1, 2""")
    conn.commit()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for t in ("agg.result_municipality", "agg.result_state", "agg.turnout_municipality", "agg.turnout_state",
                      "fact.vote_munzona", "fact.turnout_munzona", "core.section", "core.polling_place",
                      "core.vote_option", "core.candidacy"):
                cur.execute(f"ANALYZE {t}")
    finally:
        conn.autocommit = False
    out = {"result_municipality": n_mun, "result_state": n_uf, "seconds": round(time.time() - t0, 1)}
    log.info("agregados reconstruídos: %s", out)
    return out


def analyze_sections(conn: psycopg.Connection) -> None:
    # skipped_duplicate (e outros retornos cedo) podem deixar a conexão INTRANS.
    if not conn.autocommit:
        conn.commit()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("ANALYZE fact.vote_section")
            cur.execute("ANALYZE fact.turnout_section")
    finally:
        conn.autocommit = False
