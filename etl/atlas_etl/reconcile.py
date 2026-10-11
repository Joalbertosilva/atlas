"""Reconciliação de totais. Cada verificação grava linhas em meta.reconciliation."""
import json
import logging
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import psycopg

log = logging.getLogger(__name__)


def _record(cur, name: str, scope: str, expected, observed, details=None) -> bool:
    ok = expected == observed
    cur.execute(
        "INSERT INTO meta.reconciliation (check_name, scope, expected, observed, ok, details) VALUES (%s,%s,%s,%s,%s,%s)",
        (name, scope, expected, observed, ok, json.dumps(details or {}, default=str)),
    )
    return ok


def run_all(conn: psycopg.Connection, download_dir: Path) -> list[dict]:
    results: list[dict] = []
    with conn.cursor() as cur:
        # 1) Válidos: soma das opções (nominais válidos + legenda válidos + nominais convertidos) == detalhe.
        cur.execute("""
            WITH opt AS (
                SELECT v.contest_id, v.sg_uf, sum(v.qt_votos_validos) AS validos, sum(v.qt_votos) AS digitados
                FROM fact.vote_munzona v GROUP BY 1, 2),
            tur AS (
                SELECT contest_id, sg_uf, sum(qt_total_votos_validos) AS validos, sum(qt_votos_nom_convr_leg_validos) AS convr,
                       sum(qt_votos) AS votos, sum(qt_votos_nulos_tecnicos) AS tecnicos,
                       sum(qt_comparecimento) AS comparecimento
                FROM fact.turnout_munzona GROUP BY 1, 2)
            SELECT c.cd_cargo, c.sg_ue, t.sg_uf, t.validos, coalesce(o.validos, 0) + t.convr, t.votos,
                   coalesce(o.digitados, 0), t.tecnicos, t.comparecimento
            FROM tur t JOIN core.contest c ON c.id = t.contest_id LEFT JOIN opt o USING (contest_id, sg_uf)
            ORDER BY 1, 2, 3""")
        for cargo, ue, uf, exp_val, obs_val, exp_votos, obs_votos, tecnicos, comp in cur.fetchall():
            scope = f"cargo={cargo} ue={ue} uf={uf}"
            results.append({"check": "validos_opcoes_vs_detalhe", "scope": scope,
                            "ok": _record(cur, "validos_opcoes_vs_detalhe", scope, exp_val, obs_val)})
            # Nulos técnicos constam só no detalhe (não no arquivo nominal munzona): soma-se à identidade.
            results.append({"check": "votos_digitados_vs_detalhe", "scope": scope,
                            "ok": _record(cur, "votos_digitados_vs_detalhe", scope, exp_votos, obs_votos + tecnicos,
                                          {"opcoes": obs_votos, "nulos_tecnicos": tecnicos})})
            if cargo == "5":
                results.append({"check": "senador_duas_escolhas", "scope": scope,
                                "ok": _record(cur, "senador_duas_escolhas", scope, 2 * comp, exp_votos)})

        # 2) Seção x munzona por disputa e UF (mesmos votos em grãos diferentes).
        cur.execute("""
            WITH s AS (
                SELECT vs.contest_id, m.sg_uf, o.kind, sum(vs.qt_votos) AS votos
                FROM fact.vote_section vs JOIN core.section sc ON sc.id = vs.section_id
                JOIN core.municipality m ON m.cd_municipio_tse = sc.cd_municipio_tse
                JOIN core.vote_option o ON o.id = vs.option_id GROUP BY 1, 2, 3),
            z AS (
                SELECT v.contest_id, v.sg_uf, o.kind, sum(v.qt_votos) AS votos
                FROM fact.vote_munzona v JOIN core.vote_option o ON o.id = v.option_id GROUP BY 1, 2, 3)
            SELECT c.cd_cargo, c.sg_ue, s.sg_uf, s.kind, z.votos, s.votos
            FROM s JOIN core.contest c ON c.id = s.contest_id LEFT JOIN z USING (contest_id, sg_uf, kind)
            ORDER BY 1, 2, 3, 4""")
        for cargo, ue, uf, kind, munzona, secao in cur.fetchall():
            scope = f"cargo={cargo} ue={ue} uf={uf} tipo={kind}"
            results.append({"check": "secao_vs_munzona", "scope": scope,
                            "ok": _record(cur, "secao_vs_munzona", scope, munzona, secao)})

        # 3) Comparecimento: detalhe por seção x detalhe munzona.
        cur.execute("""
            WITH s AS (SELECT contest_id, sg_uf, sum(qt_comparecimento) c, sum(qt_aptos) a
                       FROM fact.turnout_section GROUP BY 1, 2),
                 z AS (SELECT contest_id, sg_uf, sum(qt_comparecimento) c, sum(qt_aptos) a
                       FROM fact.turnout_munzona GROUP BY 1, 2)
            SELECT ct.cd_cargo, ct.sg_ue, s.sg_uf, z.c, s.c, z.a, s.a
            FROM s JOIN core.contest ct ON ct.id = s.contest_id LEFT JOIN z USING (contest_id, sg_uf) ORDER BY 1, 2, 3""")
        for cargo, ue, uf, zc, sc, za, sa in cur.fetchall():
            scope = f"cargo={cargo} ue={ue} uf={uf}"
            results.append({"check": "comparecimento_secao_vs_munzona", "scope": scope,
                            "ok": _record(cur, "comparecimento_secao_vs_munzona", scope, zc, sc, {"aptos_munzona": za,
                                          "aptos_secao": sa})})

        # 4) Correspondência TSE–IBGE e geometria.
        cur.execute("""SELECT count(*) FILTER (WHERE m.cd_municipio_ibge IS NULL),
                              count(*) FILTER (WHERE m.cd_municipio_ibge IS NOT NULL AND g.cd_municipio_ibge IS NULL),
                              count(*)
                       FROM core.municipality m LEFT JOIN core.municipality_geometry g USING (cd_municipio_ibge)
                       WHERE NOT m.is_exterior""")
        no_ibge, no_geom, total = cur.fetchone()
        results.append({"check": "municipios_sem_codigo_ibge", "scope": "BR",
                        "ok": _record(cur, "municipios_sem_codigo_ibge", "BR", 0, no_ibge, {"total": total})})
        results.append({"check": "municipios_sem_geometria", "scope": "BR",
                        "ok": _record(cur, "municipios_sem_geometria", "BR", 0, no_geom, {"total": total})})

        # 5) Referência externa: relatório oficial de totalização (PDF) do Brasil.
        results.extend(_check_pdf_report(cur, download_dir))
    conn.commit()
    bad = [r for r in results if not r["ok"]]
    log.info("reconciliação: %d verificações, %d divergências", len(results), len(bad))
    return results


def _check_pdf_report(cur, download_dir: Path) -> list[dict]:
    """Extrai do PDF oficial (Presidente, Brasil) os totais de comparecimento e votos por candidatura.

    Só compara números quando o texto extraído contém o padrão esperado; caso contrário registra
    a verificação como não executada (ok=false, details.reason) em vez de supor aprovação."""
    zpath = download_dir / "Relatorio_Resultado_Totalizacao_2026_BR.zip"
    out: list[dict] = []
    if not zpath.exists() or not shutil.which("pdftotext"):
        reason = "PDF não baixado" if not zpath.exists() else "pdftotext indisponível"
        _record(cur, "relatorio_pdf_presidente", "BR", None, None, {"reason": reason})
        return [{"check": "relatorio_pdf_presidente", "scope": "BR", "ok": False, "reason": reason}]
    with zipfile.ZipFile(zpath) as z:
        name = next((n for n in z.namelist() if n.upper().endswith("PRESIDENTE.PDF")), None)
        if name is None:
            _record(cur, "relatorio_pdf_presidente", "BR", None, None, {"reason": "PDF de Presidente ausente no ZIP"})
            return [{"check": "relatorio_pdf_presidente", "scope": "BR", "ok": False}]
        pdf = z.read(name)
    text = subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf, capture_output=True, check=True,
                          timeout=60).stdout.decode("utf-8", "replace")
    cur.execute("""
        SELECT o.nr_votavel, o.label, sum(r.qt_votos_validos)
        FROM agg.result_state r JOIN core.vote_option o ON o.id = r.option_id
        JOIN core.contest c ON c.id = r.contest_id
        WHERE c.cd_cargo = '1' AND c.nr_turno = 1 AND o.kind = 'candidatura' GROUP BY 1, 2""")
    for nr, label, votes in cur.fetchall():
        formatted = f"{votes:,}".replace(",", ".")
        found = bool(re.search(rf"(?<![\d.]){re.escape(formatted)}(?![\d.])", text))
        scope = f"presidente nr={nr}"
        _record(cur, "relatorio_pdf_presidente", scope, votes, votes if found else None,
                {"label": label, "pdf_member": name, "searched": formatted})
        out.append({"check": "relatorio_pdf_presidente", "scope": scope, "ok": found})
    return out
