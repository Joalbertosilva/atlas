"""Carregadores por tipo de arquivo.

Padrão de todos: (1) staging UNLOGGED com COPY das colunas selecionadas, (2) validações,
(3) UMA transação que atualiza dimensões, substitui os fatos do recorte e grava a publicação.
Se qualquer passo falhar, a transação é desfeita e o recorte publicado anterior permanece.
"""
import json
import logging
import zlib
from collections.abc import Callable
from pathlib import Path

import psycopg

from . import db, runs
from .manifest import Resource
from .zipsafe import Member, list_members

log = logging.getLogger(__name__)

KNOWN_CARGOS = {"1", "3", "5", "6", "7", "8"}
PROPORTIONAL = ("6", "7", "8")


class ValidationError(RuntimeError):
    pass


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def _rows(cur: psycopg.Cursor, q: str, params=None) -> list[tuple]:
    cur.execute(q, params)
    return cur.fetchall()


def _one(cur: psycopg.Cursor, q: str, params=None):
    cur.execute(q, params)
    r = cur.fetchone()
    return None if r is None else r[0]


def _assert_values(cur, table: str, column: str, allowed: set[str], label: str) -> None:
    found = {r[0] for r in _rows(cur, f"SELECT DISTINCT {column} FROM staging.{table}")}
    extra = found - allowed
    _check(not extra, f"{label}: valores inesperados {sorted(extra)[:10]}")


def _upsert_elections(cur, table: str) -> None:
    cur.execute(f"""
        INSERT INTO core.election (cd_eleicao, ano_eleicao, cd_tipo_eleicao, ds_eleicao, dt_eleicao, tp_abrangencia)
        SELECT DISTINCT ON (staging.code(cd_eleicao)) staging.code(cd_eleicao), staging.to_int(ano_eleicao),
               staging.nn(cd_tipo_eleicao), ds_eleicao, staging.br_date(dt_eleicao), left(tp_abrangencia, 1)
        FROM staging.{table}
        ORDER BY staging.code(cd_eleicao)
        ON CONFLICT (cd_eleicao) DO UPDATE SET ds_eleicao = EXCLUDED.ds_eleicao, dt_eleicao = EXCLUDED.dt_eleicao,
            tp_abrangencia = EXCLUDED.tp_abrangencia""")


def _upsert_contests(cur, table: str) -> None:
    cur.execute(f"""
        INSERT INTO core.contest (cd_eleicao, nr_turno, cd_cargo, sg_ue)
        SELECT DISTINCT staging.code(cd_eleicao), staging.to_int(nr_turno), staging.code(cd_cargo), sg_ue
        FROM staging.{table}
        ON CONFLICT DO NOTHING""")


def _upsert_places_from(cur, table: str) -> None:
    """Municípios do exterior (ZZ) não estão na tabela TSE–IBGE; criados a partir dos resultados.
    Município brasileiro ausente da tabela oficial é criado sem código IBGE e reportado na cobertura."""
    cur.execute(f"""
        INSERT INTO core.municipality (cd_municipio_tse, sg_uf, nm_municipio, is_exterior)
        SELECT DISTINCT ON (staging.mun(cd_municipio)) staging.mun(cd_municipio), sg_uf, nm_municipio, sg_uf = 'ZZ'
        FROM staging.{table}
        ORDER BY staging.mun(cd_municipio)
        ON CONFLICT (cd_municipio_tse) DO NOTHING""")
    cur.execute(f"""
        INSERT INTO core.zone (sg_uf, nr_zona)
        SELECT DISTINCT sg_uf, staging.code(nr_zona) FROM staging.{table}
        ON CONFLICT DO NOTHING""")


def _member_by_suffix(path: Path, suffix: str) -> Member:
    for m in list_members(path):
        if m.name.endswith(suffix):
            return m
    raise FileNotFoundError(f"{path.name}: membro *{suffix} não encontrado")


def run_import(conn: psycopg.Connection, res: Resource, path: Path, member: Member, scope_key: str,
               body: Callable[[psycopg.Connection, runs.Run, str], dict], *, chunk_rows: int,
               columns: list[str] | None, force: bool = False) -> dict:
    runs.register_resource(conn, res, path)
    generated = runs.parse_generated(db.first_row(path, member.name)) if member.name.endswith(".csv") else None
    run = runs.begin(conn, res, path, member, scope_key, generated, force=force)
    if run is None:
        log.info("%s: conteúdo idêntico já publicado — ignorado", scope_key)
        return {"scope": scope_key, "status": "skipped_duplicate"}
    table = f"run_{run.id}_{res.kind}"
    try:
        staged = 0
        if columns is not None:
            staged = db.stage_csv(conn, table, path, member.name, columns, chunk_rows)
            log.info("%s: %d linhas em staging", scope_key, staged)
        result = body(conn, run, table) | {"staged": staged}
        conn.commit()
    except Exception as exc:
        log.error("%s: FALHOU — %s", scope_key, exc)
        runs.fail(conn, run, f"{type(exc).__name__}: {exc}")
        return {"scope": scope_key, "status": "failed", "error": str(exc)}
    db.drop_staging(conn, table)
    log.info("%s: publicado (%s)", scope_key, json.dumps(result, default=str))
    return {"scope": scope_key, "status": "published", **result}


# ---------------------------------------------------------------- TSE–IBGE
TSE_IBGE_COLS = ["CD_UF_TSE", "CD_UF_IBGE", "SG_UF", "NM_UF", "CD_MUNICIPIO_TSE", "NM_MUNICIPIO_TSE",
                 "CD_MUNICIPIO_IBGE", "NM_MUNICIPIO_IBGE"]


def load_tse_ibge(conn, res, path, *, chunk_rows, force=False):
    member = _member_by_suffix(path, "municipio_tse_ibge.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            n = _one(cur, f"SELECT count(*) FROM staging.{t}")
            dup_tse = _one(cur, f"SELECT count(*) - count(DISTINCT staging.mun(cd_municipio_tse)) FROM staging.{t}")
            dup_ibge = _one(cur, f"SELECT count(*) - count(DISTINCT cd_municipio_ibge) FROM staging.{t}")
            _check(dup_tse == 0 and dup_ibge == 0, f"códigos duplicados: tse={dup_tse} ibge={dup_ibge}")
            bad = _one(cur, f"SELECT count(*) FROM staging.{t} WHERE btrim(cd_municipio_ibge) !~ '^[0-9]{{7}}$'")
            _check(bad == 0, f"{bad} códigos IBGE fora do padrão de 7 dígitos")
            cur.execute(f"""
                INSERT INTO core.state (sg_uf, nm_uf, cd_uf_ibge, cd_uf_tse)
                SELECT DISTINCT sg_uf, nm_uf, lpad(btrim(cd_uf_ibge), 2, '0'), btrim(cd_uf_tse) FROM staging.{t}
                ON CONFLICT (sg_uf) DO UPDATE SET nm_uf = EXCLUDED.nm_uf, cd_uf_ibge = EXCLUDED.cd_uf_ibge,
                    cd_uf_tse = EXCLUDED.cd_uf_tse""")
            cur.execute(f"""
                INSERT INTO core.municipality (cd_municipio_tse, sg_uf, nm_municipio, cd_municipio_ibge, nm_municipio_ibge)
                SELECT staging.mun(cd_municipio_tse), sg_uf, nm_municipio_tse, btrim(cd_municipio_ibge), nm_municipio_ibge
                FROM staging.{t}
                ON CONFLICT (cd_municipio_tse) DO UPDATE SET sg_uf = EXCLUDED.sg_uf, nm_municipio = EXCLUDED.nm_municipio,
                    cd_municipio_ibge = EXCLUDED.cd_municipio_ibge, nm_municipio_ibge = EXCLUDED.nm_municipio_ibge""")
            validation = {"rows": n, "ufs": _one(cur, f"SELECT count(DISTINCT sg_uf) FROM staging.{t}")}
            runs.publish(cur, run, "municipio_tse_ibge", None, n, n, validation)
        return validation

    return run_import(conn, res, path, member, "ref:municipio_tse_ibge", body, chunk_rows=chunk_rows,
                      columns=TSE_IBGE_COLS, force=force)


# ---------------------------------------------------------------- Vagas
VAGAS_COLS = ["ANO_ELEICAO", "CD_TIPO_ELEICAO", "CD_ELEICAO", "DS_ELEICAO", "DT_ELEICAO", "SG_UE", "CD_CARGO",
              "DS_CARGO", "QT_VAGA"]


def load_vagas(conn, res, path, *, chunk_rows, force=False):
    member = _member_by_suffix(path, "_BRASIL.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO core.election (cd_eleicao, ano_eleicao, cd_tipo_eleicao, ds_eleicao, dt_eleicao, tp_abrangencia)
                SELECT DISTINCT ON (staging.code(cd_eleicao)) staging.code(cd_eleicao), staging.to_int(ano_eleicao),
                       staging.nn(cd_tipo_eleicao), ds_eleicao, staging.br_date(dt_eleicao),
                       CASE WHEN sg_ue = 'BR' THEN 'F' ELSE 'E' END
                FROM staging.{t} WHERE staging.code(cd_cargo) IN ('1','3','5','6','7','8')
                ORDER BY staging.code(cd_eleicao)
                ON CONFLICT (cd_eleicao) DO NOTHING""")
            cur.execute("DELETE FROM core.seat")
            cur.execute(f"""
                INSERT INTO core.seat (cd_eleicao, sg_ue, cd_cargo, qt_vaga)
                SELECT staging.code(cd_eleicao), sg_ue, staging.code(cd_cargo), staging.to_int(qt_vaga)
                FROM staging.{t} WHERE staging.code(cd_cargo) IN ('1','3','5','6','7','8')""")
            n = cur.rowcount
            total = _one(cur, f"SELECT count(*) FROM staging.{t}")
            validation = {"rows": total, "seats_rows": n}
            runs.publish(cur, run, "consulta_vagas", None, total, n, validation)
        return validation

    return run_import(conn, res, path, member, "ref:consulta_vagas", body, chunk_rows=chunk_rows,
                      columns=VAGAS_COLS, force=force)


# ---------------------------------------------------------------- Candidaturas (cadastro)
# Seleção de colunas: CPF, e-mail, título, nascimento, gênero, raça, instrução, estado civil e
# ocupação NUNCA são lidos (minimização — LGPD).
CAND_COLS = ["ANO_ELEICAO", "CD_TIPO_ELEICAO", "CD_ELEICAO", "DS_ELEICAO", "DT_ELEICAO", "TP_ABRANGENCIA",
             "NR_TURNO", "SG_UF", "SG_UE", "CD_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO",
             "NM_URNA_CANDIDATO", "CD_SITUACAO_CANDIDATURA", "DS_SITUACAO_CANDIDATURA", "NR_PARTIDO", "SG_PARTIDO",
             "NM_PARTIDO", "SG_FEDERACAO", "NM_FEDERACAO", "NM_COLIGACAO", "DS_COMPOSICAO_COLIGACAO"]


def load_candidates(conn, res, path, ue, *, chunk_rows, force=False):
    member = _member_by_suffix(path, f"consulta_cand_2026_{ue}.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            _upsert_elections(cur, t)
            cur.execute(f"""
                INSERT INTO core.candidacy (cd_eleicao, sq_candidato, cd_cargo, sg_ue, nr_candidato, nm_candidato,
                    nm_urna_candidato, nr_partido, sg_partido, nm_partido, sg_federacao, nm_federacao, nm_coligacao,
                    ds_composicao_coligacao, cd_situacao_candidatura, ds_situacao_candidatura)
                SELECT DISTINCT ON (staging.code(cd_eleicao), btrim(sq_candidato))
                       staging.code(cd_eleicao), btrim(sq_candidato), staging.code(cd_cargo), sg_ue,
                       staging.code(nr_candidato), nm_candidato, nm_urna_candidato, staging.nn(nr_partido),
                       staging.nn(sg_partido), staging.nn(nm_partido), staging.nn(sg_federacao),
                       staging.nn(nm_federacao), staging.nn(nm_coligacao), staging.nn(ds_composicao_coligacao),
                       staging.nn(cd_situacao_candidatura), staging.nn(ds_situacao_candidatura)
                FROM staging.{t}
                WHERE staging.code(cd_cargo) IN ('1','3','5','6','7','8')
                ORDER BY staging.code(cd_eleicao), btrim(sq_candidato), staging.to_int(nr_turno) DESC
                ON CONFLICT (cd_eleicao, sq_candidato) DO UPDATE SET
                    nr_candidato = EXCLUDED.nr_candidato, nm_candidato = EXCLUDED.nm_candidato,
                    nm_urna_candidato = EXCLUDED.nm_urna_candidato, nr_partido = EXCLUDED.nr_partido,
                    sg_partido = EXCLUDED.sg_partido, nm_partido = EXCLUDED.nm_partido,
                    sg_federacao = EXCLUDED.sg_federacao, nm_federacao = EXCLUDED.nm_federacao,
                    nm_coligacao = EXCLUDED.nm_coligacao, ds_composicao_coligacao = EXCLUDED.ds_composicao_coligacao""")
            n = cur.rowcount
            total = _one(cur, f"SELECT count(*) FROM staging.{t}")
            skipped = _one(cur, f"SELECT count(*) FROM staging.{t} WHERE staging.code(cd_cargo) NOT IN ('1','3','5','6','7','8')")
            validation = {"rows": total, "candidacies_upserted": n, "vice_suplente_rows_skipped": skipped}
            runs.publish(cur, run, "consulta_cand", ue, total, n, validation)
        return validation

    return run_import(conn, res, path, member, f"cand:{ue}", body, chunk_rows=chunk_rows, columns=CAND_COLS,
                      force=force)


# ---------------------------------------------------------------- Votos por candidatura munzona
MUNZONA_CAND_COLS = ["ANO_ELEICAO", "CD_TIPO_ELEICAO", "NR_TURNO", "CD_ELEICAO", "DS_ELEICAO", "DT_ELEICAO",
                     "TP_ABRANGENCIA", "SG_UF", "SG_UE", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "CD_CARGO",
                     "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO",
                     "CD_SITUACAO_CANDIDATURA", "DS_SITUACAO_CANDIDATURA", "DS_DETALHE_SITUACAO_CAND",
                     "NR_PARTIDO", "SG_PARTIDO", "NM_PARTIDO", "SG_FEDERACAO", "NM_FEDERACAO", "NM_COLIGACAO",
                     "DS_COMPOSICAO_COLIGACAO", "ST_VOTO_EM_TRANSITO", "QT_VOTOS_NOMINAIS",
                     "NM_TIPO_DESTINACAO_VOTOS", "QT_VOTOS_NOMINAIS_VALIDOS", "CD_SIT_TOT_TURNO", "DS_SIT_TOT_TURNO"]


def load_munzona_cand(conn, res, path, ue, *, chunk_rows, force=False):
    member = _member_by_suffix(path, f"votacao_candidato_munzona_2026_{ue}.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            cur.execute("SET LOCAL enable_nestloop = off")
            _assert_values(cur, t, "sg_ue", {ue}, "SG_UE")
            _assert_values(cur, t, "staging.code(cd_cargo)", KNOWN_CARGOS, "CD_CARGO")
            _assert_values(cur, t, "st_voto_em_transito", {"N", "S"}, "ST_VOTO_EM_TRANSITO")
            _upsert_elections(cur, t)
            _upsert_contests(cur, t)
            _upsert_places_from(cur, t)
            cur.execute(f"""
                INSERT INTO core.candidacy (cd_eleicao, sq_candidato, cd_cargo, sg_ue, nr_candidato, nm_candidato,
                    nm_urna_candidato, nr_partido, sg_partido, nm_partido, sg_federacao, nm_federacao, nm_coligacao,
                    ds_composicao_coligacao, cd_situacao_candidatura, ds_situacao_candidatura, ds_detalhe_situacao_cand)
                SELECT DISTINCT ON (staging.code(cd_eleicao), btrim(sq_candidato))
                       staging.code(cd_eleicao), btrim(sq_candidato), staging.code(cd_cargo), sg_ue,
                       staging.code(nr_candidato), nm_candidato, nm_urna_candidato, staging.nn(nr_partido),
                       staging.nn(sg_partido), staging.nn(nm_partido), staging.nn(sg_federacao), staging.nn(nm_federacao),
                       staging.nn(nm_coligacao), staging.nn(ds_composicao_coligacao),
                       staging.nn(cd_situacao_candidatura), staging.nn(ds_situacao_candidatura),
                       staging.nn(ds_detalhe_situacao_cand)
                FROM staging.{t}
                ORDER BY staging.code(cd_eleicao), btrim(sq_candidato)
                ON CONFLICT (cd_eleicao, sq_candidato) DO UPDATE SET
                    ds_detalhe_situacao_cand = EXCLUDED.ds_detalhe_situacao_cand,
                    cd_situacao_candidatura = COALESCE(EXCLUDED.cd_situacao_candidatura, core.candidacy.cd_situacao_candidatura),
                    ds_situacao_candidatura = COALESCE(EXCLUDED.ds_situacao_candidatura, core.candidacy.ds_situacao_candidatura)""")
            # Situação por turno: um valor por candidatura no arquivo; divergência = erro de layout.
            div = _one(cur, f"""SELECT count(*) FROM (SELECT sq_candidato, nr_turno FROM staging.{t}
                       GROUP BY 1,2 HAVING count(DISTINCT ds_sit_tot_turno) > 1
                          OR count(DISTINCT nm_tipo_destinacao_votos) > 1) x""")
            _check(div == 0, f"{div} candidaturas com situação/destinação divergente entre linhas")
            cur.execute(f"""
                INSERT INTO core.candidacy_round (candidacy_id, nr_turno, nm_tipo_destinacao_votos, cd_sit_tot_turno, ds_sit_tot_turno)
                SELECT DISTINCT ON (c.id, staging.to_int(s.nr_turno)) c.id, staging.to_int(s.nr_turno),
                       staging.nn(s.nm_tipo_destinacao_votos), staging.nn(s.cd_sit_tot_turno), staging.nn(s.ds_sit_tot_turno)
                FROM staging.{t} s
                JOIN core.candidacy c ON c.cd_eleicao = staging.code(s.cd_eleicao) AND c.sq_candidato = btrim(s.sq_candidato)
                ORDER BY c.id, staging.to_int(s.nr_turno)
                ON CONFLICT (candidacy_id, nr_turno) DO UPDATE SET
                    nm_tipo_destinacao_votos = EXCLUDED.nm_tipo_destinacao_votos,
                    cd_sit_tot_turno = EXCLUDED.cd_sit_tot_turno, ds_sit_tot_turno = EXCLUDED.ds_sit_tot_turno""")
            cur.execute(f"""
                INSERT INTO core.vote_option (cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, sq_candidato, candidacy_id,
                                              nr_partido, label)
                SELECT DISTINCT ON (c.id) c.cd_eleicao, c.cd_cargo, c.sg_ue, 'candidatura', c.nr_candidato,
                       c.sq_candidato, c.id, c.nr_partido, c.nm_urna_candidato
                FROM staging.{t} s
                JOIN core.candidacy c ON c.cd_eleicao = staging.code(s.cd_eleicao) AND c.sq_candidato = btrim(s.sq_candidato)
                ORDER BY c.id
                ON CONFLICT (cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, sq_candidato)
                DO UPDATE SET label = EXCLUDED.label, nr_partido = EXCLUDED.nr_partido""")
            cur.execute("""
                DELETE FROM fact.vote_munzona v USING core.vote_option o, core.contest c
                WHERE v.option_id = o.id AND o.kind = 'candidatura' AND v.contest_id = c.id AND c.sg_ue = %s""", (ue,))
            cur.execute(f"""
                INSERT INTO fact.vote_munzona (contest_id, sg_uf, cd_municipio_tse, nr_zona, option_id,
                                               st_voto_em_transito, qt_votos, qt_votos_validos)
                SELECT ct.id, s.sg_uf, staging.mun(s.cd_municipio), staging.code(s.nr_zona), o.id,
                       s.st_voto_em_transito = 'S', staging.to_int(s.qt_votos_nominais),
                       staging.to_int(s.qt_votos_nominais_validos)
                FROM staging.{t} s
                JOIN core.contest ct ON ct.cd_eleicao = staging.code(s.cd_eleicao)
                     AND ct.nr_turno = staging.to_int(s.nr_turno) AND ct.cd_cargo = staging.code(s.cd_cargo)
                     AND ct.sg_ue = s.sg_ue
                JOIN core.vote_option o ON o.kind = 'candidatura' AND o.cd_eleicao = ct.cd_eleicao
                     AND o.sq_candidato = btrim(s.sq_candidato) AND o.cd_cargo = ct.cd_cargo AND o.sg_ue = ct.sg_ue""")
            loaded = cur.rowcount
            staged, votes = _rows(cur, f"SELECT count(*), sum(staging.to_int(qt_votos_nominais)) FROM staging.{t}")[0]
            _check(loaded == staged, f"linhas publicadas {loaded} != staging {staged}")
            validation = {"rows": staged, "qt_votos_nominais": int(votes or 0)}
            runs.publish(cur, run, "munzona_cand", ue, staged, loaded, validation)
        return validation

    return run_import(conn, res, path, member, f"munzona_cand:{ue}", body, chunk_rows=chunk_rows,
                      columns=MUNZONA_CAND_COLS, force=force)


# ---------------------------------------------------------------- Legenda munzona
PARTIDO_COLS = ["CD_ELEICAO", "NR_TURNO", "CD_CARGO", "SG_UF", "SG_UE", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA",
                "NR_PARTIDO", "SG_PARTIDO", "ST_VOTO_EM_TRANSITO", "QT_VOTOS_LEGENDA_VALIDOS",
                "QT_VOTOS_NOM_CONVR_LEG_VALIDOS", "QT_VOTOS_LEGENDA_ANUL_SUBJUD", "QT_VOTOS_LEGENDA_ANULADOS"]


def load_munzona_partido(conn, res, path, ue, *, chunk_rows, force=False):
    member = _member_by_suffix(path, f"votacao_partido_munzona_2026_{ue}.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            _assert_values(cur, t, "sg_ue", {ue}, "SG_UE")
            _upsert_contests(cur, t)
            _upsert_places_from(cur, t)
            prop = f"staging.code(cd_cargo) IN {PROPORTIONAL}"
            cur.execute(f"""
                INSERT INTO core.vote_option (cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, nr_partido, label)
                SELECT DISTINCT staging.code(cd_eleicao), staging.code(cd_cargo), sg_ue, 'legenda',
                       staging.code(nr_partido), staging.code(nr_partido), sg_partido || ' (legenda)'
                FROM staging.{t} WHERE {prop}
                ON CONFLICT (cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, sq_candidato) DO NOTHING""")
            cur.execute("""
                DELETE FROM fact.vote_munzona v USING core.vote_option o, core.contest c
                WHERE v.option_id = o.id AND o.kind = 'legenda' AND v.contest_id = c.id AND c.sg_ue = %s""", (ue,))
            # Legenda: votos digitados para o número do partido (válidos + anulados).
            # QT_VOTOS_NOM_CONVR_LEG_VALIDOS (nominais convertidos) fica registrado na validação/turnout.
            cur.execute(f"""
                INSERT INTO fact.vote_munzona (contest_id, sg_uf, cd_municipio_tse, nr_zona, option_id,
                                               st_voto_em_transito, qt_votos, qt_votos_validos)
                SELECT ct.id, s.sg_uf, staging.mun(s.cd_municipio), staging.code(s.nr_zona), o.id,
                       s.st_voto_em_transito = 'S',
                       sum(staging.to_int(s.qt_votos_legenda_validos) + staging.to_int(s.qt_votos_legenda_anul_subjud)
                           + staging.to_int(s.qt_votos_legenda_anulados)),
                       sum(staging.to_int(s.qt_votos_legenda_validos))
                FROM staging.{t} s
                JOIN core.contest ct ON ct.cd_eleicao = staging.code(s.cd_eleicao)
                     AND ct.nr_turno = staging.to_int(s.nr_turno) AND ct.cd_cargo = staging.code(s.cd_cargo)
                     AND ct.sg_ue = s.sg_ue
                JOIN core.vote_option o ON o.kind = 'legenda' AND o.cd_eleicao = ct.cd_eleicao
                     AND o.cd_cargo = ct.cd_cargo AND o.sg_ue = ct.sg_ue AND o.nr_votavel = staging.code(s.nr_partido)
                WHERE {prop.replace('cd_cargo', 's.cd_cargo')}
                GROUP BY 1,2,3,4,5,6
                HAVING sum(staging.to_int(s.qt_votos_legenda_validos) + staging.to_int(s.qt_votos_legenda_anul_subjud)
                           + staging.to_int(s.qt_votos_legenda_anulados)) > 0""")
            loaded = cur.rowcount
            staged = _one(cur, f"SELECT count(*) FROM staging.{t}")
            convr = _one(cur, f"SELECT coalesce(sum(staging.to_int(qt_votos_nom_convr_leg_validos)),0) FROM staging.{t}")
            leg = _one(cur, f"""SELECT coalesce(sum(staging.to_int(qt_votos_legenda_validos)),0) FROM staging.{t}
                               WHERE {prop}""")
            validation = {"rows": staged, "legenda_rows_nonzero": loaded, "qt_votos_legenda_validos": int(leg),
                          "qt_votos_nom_convr_leg_validos": int(convr)}
            runs.publish(cur, run, "munzona_partido", ue, staged, loaded, validation)
        return validation

    return run_import(conn, res, path, member, f"munzona_partido:{ue}", body, chunk_rows=chunk_rows,
                      columns=PARTIDO_COLS, force=force)


# ---------------------------------------------------------------- Detalhe munzona (comparecimento, brancos, nulos)
DETALHE_COLS = ["CD_ELEICAO", "NR_TURNO", "CD_CARGO", "SG_UF", "SG_UE", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA",
                "QT_APTOS", "QT_SECOES_PRINCIPAIS", "QT_SECOES_AGREGADAS", "QT_SECOES_NAO_INSTALADAS",
                "QT_TOTAL_SECOES", "QT_COMPARECIMENTO", "QT_ELEITORES_SECOES_NAO_INSTALADAS", "QT_ABSTENCOES",
                "ST_VOTO_EM_TRANSITO", "QT_VOTOS", "QT_VOTOS_CONCORRENTES", "QT_TOTAL_VOTOS_VALIDOS",
                "QT_VOTOS_NOMINAIS_VALIDOS", "QT_TOTAL_VOTOS_LEG_VALIDOS", "QT_VOTOS_LEG_VALIDOS",
                "QT_VOTOS_NOM_CONVR_LEG_VALIDOS", "QT_TOTAL_VOTOS_ANULADOS", "QT_TOTAL_VOTOS_ANUL_SUBJUD",
                "QT_VOTOS_BRANCOS", "QT_TOTAL_VOTOS_NULOS", "QT_VOTOS_NULOS", "QT_VOTOS_NULOS_TECNICOS",
                "QT_VOTOS_ANULADOS_APU_SEP", "HH_ULTIMA_TOTALIZACAO", "DT_ULTIMA_TOTALIZACAO"]
_TURNOUT_INT = [c.lower() for c in DETALHE_COLS if c.startswith("QT_")]


def load_detalhe_munzona(conn, res, path, ue, *, chunk_rows, force=False):
    member = _member_by_suffix(path, f"detalhe_votacao_munzona_2026_{ue}.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            _assert_values(cur, t, "sg_ue", {ue}, "SG_UE")
            _assert_values(cur, t, "staging.code(cd_cargo)", KNOWN_CARGOS, "CD_CARGO")
            _upsert_contests(cur, t)
            _upsert_places_from(cur, t)
            bad = _one(cur, f"""SELECT count(*) FROM staging.{t}
                WHERE staging.to_int(qt_comparecimento) + staging.to_int(qt_abstencoes)
                      + staging.to_int(qt_eleitores_secoes_nao_instaladas) <> staging.to_int(qt_aptos)
                   OR staging.to_int(qt_comparecimento) > staging.to_int(qt_aptos)""")
            _check(bad == 0, f"{bad} linhas com aptos != comparecimento + abstenções + eleitores de seções não instaladas")
            cur.execute("DELETE FROM fact.turnout_munzona t USING core.contest c WHERE t.contest_id = c.id AND c.sg_ue = %s",
                        (ue,))
            ints = ", ".join(f"staging.to_int(s.{c})" for c in _TURNOUT_INT)
            cur.execute(f"""
                INSERT INTO fact.turnout_munzona (contest_id, sg_uf, cd_municipio_tse, nr_zona, st_voto_em_transito,
                    {", ".join(_TURNOUT_INT)}, dt_ultima_totalizacao)
                SELECT ct.id, s.sg_uf, staging.mun(s.cd_municipio), staging.code(s.nr_zona), s.st_voto_em_transito = 'S',
                       {ints},
                       to_timestamp(staging.nn(s.dt_ultima_totalizacao) || ' ' || staging.nn(s.hh_ultima_totalizacao),
                                    'DD/MM/YYYY HH24:MI:SS')::timestamp
                FROM staging.{t} s
                JOIN core.contest ct ON ct.cd_eleicao = staging.code(s.cd_eleicao)
                     AND ct.nr_turno = staging.to_int(s.nr_turno) AND ct.cd_cargo = staging.code(s.cd_cargo)
                     AND ct.sg_ue = s.sg_ue""")
            loaded = cur.rowcount
            cur.execute(f"""
                INSERT INTO core.vote_option (cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, label)
                SELECT DISTINCT staging.code(cd_eleicao), staging.code(cd_cargo), sg_ue, k.kind, k.nr, k.label
                FROM staging.{t}
                CROSS JOIN (VALUES ('branco','95','Voto em branco'), ('nulo','96','Voto nulo')) AS k(kind, nr, label)
                ON CONFLICT (cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, sq_candidato) DO NOTHING""")
            cur.execute("""
                DELETE FROM fact.vote_munzona v USING core.vote_option o, core.contest c
                WHERE v.option_id = o.id AND o.kind IN ('branco','nulo') AND v.contest_id = c.id AND c.sg_ue = %s""",
                        (ue,))
            # Nulo = QT_VOTOS_NULOS (digitação nula). Nulos técnicos pertencem a candidaturas (arquivo nominal).
            cur.execute("""
                INSERT INTO fact.vote_munzona (contest_id, sg_uf, cd_municipio_tse, nr_zona, option_id,
                                               st_voto_em_transito, qt_votos, qt_votos_validos)
                SELECT t.contest_id, t.sg_uf, t.cd_municipio_tse, t.nr_zona, o.id, t.st_voto_em_transito,
                       CASE o.kind WHEN 'branco' THEN t.qt_votos_brancos ELSE t.qt_votos_nulos END, 0
                FROM fact.turnout_munzona t
                JOIN core.contest c ON c.id = t.contest_id AND c.sg_ue = %s
                JOIN core.vote_option o ON o.cd_eleicao = c.cd_eleicao AND o.cd_cargo = c.cd_cargo
                     AND o.sg_ue = c.sg_ue AND o.kind IN ('branco','nulo')""", (ue,))
            staged = _one(cur, f"SELECT count(*) FROM staging.{t}")
            _check(loaded == staged, f"turnout publicado {loaded} != staging {staged}")
            validation = {"rows": staged}
            runs.publish(cur, run, "munzona_detalhe", ue, staged, loaded, validation)
        return validation

    return run_import(conn, res, path, member, f"munzona_detalhe:{ue}", body, chunk_rows=chunk_rows,
                      columns=DETALHE_COLS, force=force)


# ---------------------------------------------------------------- Votação por seção
SECAO_COLS = ["CD_ELEICAO", "NR_TURNO", "CD_CARGO", "SG_UF", "SG_UE", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA",
              "NR_SECAO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS", "NR_LOCAL_VOTACAO", "SQ_CANDIDATO"]


def load_secao(conn, res, path, ue, *, chunk_rows, force=False):
    member = _member_by_suffix(path, f"votacao_secao_2026_{ue}.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            cur.execute("SET LOCAL work_mem = '256MB'")
            # Junções em várias colunas correlacionadas levam o planejador a estimar 1 linha e
            # escolher nested loop (5,8 s vs 2,2 s medidos no AC). Carga em lote: só hash/merge.
            cur.execute("SET LOCAL enable_nestloop = off")
            staged = _one(cur, f"SELECT count(*) FROM staging.{t}")
            if staged == 0:
                cur.execute(f"TRUNCATE fact.vote_section_{ue.lower()}")
                validation = {"rows": 0, "note": "arquivo oficial sem linhas de dados"}
                runs.publish(cur, run, "secao", ue, 0, 0, validation)
                return validation
            _assert_values(cur, t, "sg_ue", {ue}, "SG_UE")
            _assert_values(cur, t, "staging.code(cd_cargo)", KNOWN_CARGOS, "CD_CARGO")
            _upsert_contests(cur, t)
            _upsert_places_from(cur, t)
            # Normaliza uma vez (evita recalcular funções em cada JOIN).
            cur.execute(f"""
                CREATE TEMP TABLE sec_norm ON COMMIT DROP AS
                SELECT staging.code(cd_eleicao) AS cd_eleicao, staging.to_int(nr_turno)::smallint AS nr_turno,
                       staging.code(cd_cargo) AS cd_cargo, sg_ue, staging.mun(cd_municipio) AS cd_mun,
                       staging.code(nr_zona) AS nr_zona, staging.code(nr_secao) AS nr_secao,
                       staging.code(nr_votavel) AS nr_votavel, btrim(sq_candidato) AS sq, nm_votavel,
                       staging.to_int(qt_votos) AS qt_votos, staging.code(nr_local_votacao) AS nr_local,
                       CASE WHEN staging.code(nr_votavel) = '95' THEN 'branco' WHEN staging.code(nr_votavel) = '96' THEN 'nulo'
                            WHEN btrim(sq_candidato) = '' OR btrim(sq_candidato) LIKE '-%' THEN 'legenda'
                            ELSE 'candidatura' END AS kind
                FROM staging.{t}""")
            cur.execute("ALTER TABLE sec_norm ADD COLUMN sq_key text")
            cur.execute("UPDATE sec_norm SET sq_key = CASE WHEN kind = 'candidatura' THEN sq ELSE '' END")
            cur.execute("ANALYZE sec_norm")
            multi = _one(cur, """SELECT count(*) FROM (SELECT 1 FROM sec_norm GROUP BY cd_mun, nr_zona, nr_secao
                                 HAVING min(nr_local) <> max(nr_local)) x""")
            cur.execute("""
                INSERT INTO core.section (cd_municipio_tse, nr_zona, nr_secao, result_nr_local)
                SELECT cd_mun, nr_zona, nr_secao, min(nr_local) FROM sec_norm GROUP BY 1,2,3
                ON CONFLICT (cd_municipio_tse, nr_zona, nr_secao)
                DO UPDATE SET result_nr_local = EXCLUDED.result_nr_local""")
            cur.execute("""
                CREATE TEMP TABLE sec_opt ON COMMIT DROP AS
                SELECT DISTINCT cd_eleicao, cd_cargo, sg_ue, nr_votavel, sq, nm_votavel, kind FROM sec_norm""")
            missing = _one(cur, """SELECT count(*) FROM sec_opt o LEFT JOIN core.candidacy c
                       ON c.cd_eleicao = o.cd_eleicao AND c.sq_candidato = o.sq
                       WHERE o.kind = 'candidatura' AND c.id IS NULL""")
            _check(missing == 0, f"{missing} candidaturas da seção ausentes do cadastro/munzona (importe-os antes)")
            cur.execute("""
                INSERT INTO core.vote_option (cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, sq_candidato, candidacy_id,
                                              nr_partido, label)
                SELECT o.cd_eleicao, o.cd_cargo, o.sg_ue, o.kind, o.nr_votavel,
                       CASE WHEN o.kind = 'candidatura' THEN o.sq ELSE '' END, c.id,
                       CASE WHEN o.kind = 'legenda' THEN o.nr_votavel ELSE c.nr_partido END,
                       CASE o.kind WHEN 'candidatura' THEN c.nm_urna_candidato WHEN 'branco' THEN 'Voto em branco'
                                   WHEN 'nulo' THEN 'Voto nulo' ELSE o.nm_votavel || ' (legenda)' END
                FROM sec_opt o
                LEFT JOIN core.candidacy c ON o.kind = 'candidatura' AND c.cd_eleicao = o.cd_eleicao AND c.sq_candidato = o.sq
                ON CONFLICT (cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, sq_candidato) DO NOTHING""")
            cur.execute(f"TRUNCATE fact.vote_section_{ue.lower()}")
            cur.execute("""
                INSERT INTO fact.vote_section (sg_ue, contest_id, section_id, option_id, qt_votos)
                SELECT n.sg_ue, ct.id, s.id, o.id, n.qt_votos
                FROM sec_norm n
                JOIN core.contest ct ON ct.cd_eleicao = n.cd_eleicao AND ct.nr_turno = n.nr_turno
                     AND ct.cd_cargo = n.cd_cargo AND ct.sg_ue = n.sg_ue
                JOIN core.section s ON s.cd_municipio_tse = n.cd_mun AND s.nr_zona = n.nr_zona AND s.nr_secao = n.nr_secao
                JOIN core.vote_option o ON o.cd_eleicao = n.cd_eleicao AND o.cd_cargo = n.cd_cargo AND o.sg_ue = n.sg_ue
                     AND o.nr_votavel = n.nr_votavel AND o.sq_candidato = n.sq_key AND o.kind = n.kind""")
            loaded = cur.rowcount
            _check(loaded == staged, f"linhas publicadas {loaded} != staging {staged} (JOIN perdeu/multiplicou linhas)")
            refresh_links(cur, None if ue == "BR" else ue)
            votes = _one(cur, "SELECT sum(qt_votos) FROM sec_norm")
            validation = {"rows": staged, "qt_votos": int(votes), "sections_with_multiple_locals": multi,
                          "sections": _one(cur, "SELECT count(*) FROM (SELECT DISTINCT cd_mun, nr_zona, nr_secao FROM sec_norm) x")}
            runs.publish(cur, run, "secao", ue, staged, loaded, validation)
        return validation

    return run_import(conn, res, path, member, f"secao:{ue}", body, chunk_rows=chunk_rows, columns=SECAO_COLS,
                      force=force)


# ---------------------------------------------------------------- Detalhe por seção
DETALHE_SECAO_COLS = ["CD_ELEICAO", "NR_TURNO", "CD_CARGO", "SG_UF", "SG_UE", "CD_MUNICIPIO", "NM_MUNICIPIO",
                      "NR_ZONA", "NR_SECAO", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_NOMINAIS",
                      "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "QT_VOTOS_LEGENDA", "QT_VOTOS_ANULADOS_APU_SEP",
                      "DS_ORIGEM_VOTO", "ST_SECAO_INSTALADA", "ST_SECAO_ANULADA"]


def load_detalhe_secao(conn, res, path, ue, *, chunk_rows, force=False):
    member = _member_by_suffix(path, f"detalhe_votacao_secao_2026_{ue}.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            cur.execute("SET LOCAL enable_nestloop = off")
            staged = _one(cur, f"SELECT count(*) FROM staging.{t}")
            cur.execute("""DELETE FROM fact.turnout_section ts USING core.contest c
                           WHERE ts.contest_id = c.id AND c.sg_ue = %s""", (ue,))
            if staged == 0:
                validation = {"rows": 0, "note": "arquivo oficial sem linhas de dados"}
                runs.publish(cur, run, "detalhe_secao", ue, 0, 0, validation)
                return validation
            _assert_values(cur, t, "sg_ue", {ue}, "SG_UE")
            _upsert_contests(cur, t)
            _upsert_places_from(cur, t)
            cur.execute(f"""
                INSERT INTO core.section (cd_municipio_tse, nr_zona, nr_secao)
                SELECT DISTINCT staging.mun(cd_municipio), staging.code(nr_zona), staging.code(nr_secao) FROM staging.{t}
                ON CONFLICT DO NOTHING""")
            cur.execute(f"""
                INSERT INTO fact.turnout_section (contest_id, section_id, sg_uf, qt_aptos, qt_comparecimento, qt_abstencoes,
                    qt_votos_nominais, qt_votos_brancos, qt_votos_nulos, qt_votos_legenda, qt_votos_anulados_apu_sep,
                    ds_origem_voto, st_secao_instalada, st_secao_anulada)
                SELECT ct.id, s.id, d.sg_uf, staging.to_int(d.qt_aptos), staging.to_int(d.qt_comparecimento),
                       staging.to_int(d.qt_abstencoes), staging.to_int(d.qt_votos_nominais),
                       staging.to_int(d.qt_votos_brancos), staging.to_int(d.qt_votos_nulos),
                       staging.to_int(d.qt_votos_legenda), staging.to_int(d.qt_votos_anulados_apu_sep),
                       staging.nn(d.ds_origem_voto), staging.nn(d.st_secao_instalada) = 'Sim',
                       staging.nn(d.st_secao_anulada) = 'Sim'
                FROM staging.{t} d
                JOIN core.contest ct ON ct.cd_eleicao = staging.code(d.cd_eleicao)
                     AND ct.nr_turno = staging.to_int(d.nr_turno) AND ct.cd_cargo = staging.code(d.cd_cargo)
                     AND ct.sg_ue = d.sg_ue
                JOIN core.section s ON s.cd_municipio_tse = staging.mun(d.cd_municipio)
                     AND s.nr_zona = staging.code(d.nr_zona) AND s.nr_secao = staging.code(d.nr_secao)""")
            loaded = cur.rowcount
            _check(loaded == staged, f"linhas publicadas {loaded} != staging {staged}")
            validation = {"rows": staged}
            runs.publish(cur, run, "detalhe_secao", ue, staged, loaded, validation)
        return validation

    return run_import(conn, res, path, member, f"detalhe_secao:{ue}", body, chunk_rows=chunk_rows,
                      columns=DETALHE_SECAO_COLS, force=force)


# ---------------------------------------------------------------- Locais de votação
LOCAIS_COLS = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_TIPO_SECAO_AGREGADA",
               "DS_TIPO_SECAO_AGREGADA", "NR_SECAO_PRINCIPAL", "NR_LOCAL_VOTACAO", "NM_LOCAL_VOTACAO",
               "CD_TIPO_LOCAL", "DS_TIPO_LOCAL", "DS_ENDERECO", "NM_BAIRRO", "NR_CEP", "NR_LATITUDE", "NR_LONGITUDE",
               "DS_SITU_LOCAL_VOTACAO", "QT_ELEITOR_SECAO"]
# Telefone do local (NR_TELEFONE_LOCAL) não é lido: desnecessário para a finalidade.


def load_locais(conn, res, path, uf, *, chunk_rows, force=False):
    member = _member_by_suffix(path, f"eleitorado_local_votacao_2026_{uf}.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            _assert_values(cur, t, "sg_uf", {uf}, "SG_UF")
            cur.execute(f"""
                CREATE TEMP TABLE loc ON COMMIT DROP AS
                SELECT staging.mun(cd_municipio) AS cd_mun, sg_uf, nm_municipio, staging.code(nr_zona) AS nr_zona,
                       staging.code(nr_secao) AS nr_secao, staging.nn(cd_tipo_secao_agregada) AS cd_agr,
                       staging.nn(ds_tipo_secao_agregada) AS ds_agr,
                       CASE WHEN staging.code(nr_secao_principal) = '-1' THEN NULL ELSE staging.code(nr_secao_principal) END AS principal,
                       staging.code(nr_local_votacao) AS nr_local, nm_local_votacao, staging.nn(cd_tipo_local) AS cd_tipo,
                       staging.nn(ds_tipo_local) AS ds_tipo, staging.nn(ds_endereco) AS endereco,
                       staging.nn(nm_bairro) AS bairro, staging.nn(nr_cep) AS cep, staging.nn(ds_situ_local_votacao) AS situ,
                       CASE WHEN replace(btrim(nr_latitude), ',', '.') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                            THEN replace(btrim(nr_latitude), ',', '.')::double precision END AS lat,
                       CASE WHEN replace(btrim(nr_longitude), ',', '.') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                            THEN replace(btrim(nr_longitude), ',', '.')::double precision END AS lon,
                       staging.to_int(qt_eleitor_secao) AS qt_eleitor
                FROM staging.{t} WHERE staging.to_int(nr_turno) = 1""")
            dup = _one(cur, """SELECT count(*) FROM (SELECT 1 FROM loc GROUP BY cd_mun, nr_zona, nr_secao
                               HAVING count(*) > 1) x""")
            _check(dup == 0, f"{dup} seções com mais de um local no cadastro (multiplicidade inesperada)")
            names = _one(cur, """SELECT count(*) FROM (SELECT 1 FROM loc GROUP BY cd_mun, nr_zona, nr_local
                                 HAVING count(DISTINCT nm_local_votacao) > 1) x""")
            cur.execute("""
                INSERT INTO core.municipality (cd_municipio_tse, sg_uf, nm_municipio, is_exterior)
                SELECT DISTINCT ON (cd_mun) cd_mun, sg_uf, nm_municipio, sg_uf = 'ZZ' FROM loc ORDER BY cd_mun
                ON CONFLICT DO NOTHING""")
            cur.execute("""
                INSERT INTO core.polling_place (cd_municipio_tse, nr_zona, nr_local_votacao, nm_local_votacao, cd_tipo_local,
                    ds_tipo_local, ds_endereco, nm_bairro, nr_cep, ds_situ_local, latitude, longitude, coord_status, geom)
                SELECT DISTINCT ON (cd_mun, nr_zona, nr_local) cd_mun, nr_zona, nr_local, nm_local_votacao, cd_tipo, ds_tipo,
                       endereco, bairro, cep, situ, lat, lon, x.status,
                       CASE WHEN x.status = 'valida' THEN ST_SetSRID(ST_MakePoint(lon, lat), 4326) END
                FROM loc
                CROSS JOIN LATERAL (SELECT CASE
                    WHEN lat IS NULL OR lon IS NULL OR (lat = -1 AND lon = -1) OR (lat = 0 AND lon = 0) THEN 'ausente'
                    WHEN sg_uf <> 'ZZ' AND lat BETWEEN -34.0 AND 5.6 AND lon BETWEEN -74.1 AND -28.6 THEN 'valida'
                    WHEN sg_uf = 'ZZ' AND lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180 THEN 'valida'
                    ELSE 'invalida' END AS status) x
                ORDER BY cd_mun, nr_zona, nr_local
                ON CONFLICT (cd_municipio_tse, nr_zona, nr_local_votacao) DO UPDATE SET
                    nm_local_votacao = EXCLUDED.nm_local_votacao, cd_tipo_local = EXCLUDED.cd_tipo_local,
                    ds_tipo_local = EXCLUDED.ds_tipo_local, ds_endereco = EXCLUDED.ds_endereco,
                    nm_bairro = EXCLUDED.nm_bairro, nr_cep = EXCLUDED.nr_cep, ds_situ_local = EXCLUDED.ds_situ_local,
                    latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
                    coord_status = EXCLUDED.coord_status, geom = EXCLUDED.geom""")
            places = cur.rowcount
            cur.execute("""
                INSERT INTO core.section (cd_municipio_tse, nr_zona, nr_secao, polling_place_id, cd_tipo_secao_agregada,
                                          ds_tipo_secao_agregada, nr_secao_principal, qt_eleitor_secao)
                SELECT l.cd_mun, l.nr_zona, l.nr_secao, p.id, l.cd_agr, l.ds_agr, l.principal, l.qt_eleitor
                FROM loc l JOIN core.polling_place p ON p.cd_municipio_tse = l.cd_mun AND p.nr_zona = l.nr_zona
                     AND p.nr_local_votacao = l.nr_local
                ON CONFLICT (cd_municipio_tse, nr_zona, nr_secao) DO UPDATE SET
                    polling_place_id = EXCLUDED.polling_place_id, cd_tipo_secao_agregada = EXCLUDED.cd_tipo_secao_agregada,
                    ds_tipo_secao_agregada = EXCLUDED.ds_tipo_secao_agregada,
                    nr_secao_principal = EXCLUDED.nr_secao_principal, qt_eleitor_secao = EXCLUDED.qt_eleitor_secao""")
            sections = cur.rowcount
            refresh_links(cur, uf)
            staged = _one(cur, f"SELECT count(*) FROM staging.{t}")
            validation = {"rows": staged, "turno1_rows": _one(cur, "SELECT count(*) FROM loc"), "polling_places": places,
                          "sections": sections, "local_keys_with_multiple_names": names,
                          "coord_status": dict(_rows(cur, """SELECT x.status, count(DISTINCT (cd_mun,nr_zona,nr_local))
                              FROM loc CROSS JOIN LATERAL (SELECT CASE WHEN lat IS NULL OR lon IS NULL
                              OR (lat=-1 AND lon=-1) OR (lat=0 AND lon=0) THEN 'ausente' ELSE 'informada' END status) x
                              GROUP BY 1"""))}
            runs.publish(cur, run, "locais", uf, staged, sections, validation)
        return validation

    return run_import(conn, res, path, member, f"locais:{uf}", body, chunk_rows=chunk_rows, columns=LOCAIS_COLS,
                      force=force)


def refresh_links(cur, uf: str | None) -> None:
    """Classifica o vínculo seção–local comparando o cadastro (eleitorado_local_votacao) com o
    NR_LOCAL_VOTACAO informado no próprio arquivo de resultados da seção. Sem casamento por nome."""
    cur.execute("""
        WITH x AS (
            SELECT s.id, CASE
                WHEN p.id IS NOT NULL AND s.result_nr_local IS NOT NULL AND p.nr_local_votacao = s.result_nr_local
                    THEN 'confirmado'
                WHEN p.id IS NOT NULL AND s.result_nr_local IS NOT NULL THEN 'divergente'
                WHEN p.id IS NOT NULL THEN 'somente_cadastro'
                WHEN s.result_nr_local IS NOT NULL THEN 'somente_resultado'
                ELSE 'sem_vinculo' END AS st
            FROM core.section s
            JOIN core.municipality m ON m.cd_municipio_tse = s.cd_municipio_tse
            LEFT JOIN core.polling_place p ON p.id = s.polling_place_id
            WHERE %(uf)s::text IS NULL OR m.sg_uf = %(uf)s::text)
        UPDATE core.section s SET link_status = x.st FROM x WHERE x.id = s.id AND s.link_status <> x.st""",
                {"uf": uf})


# ---------------------------------------------------------------- Pesquisas registradas
# NM_ESTATISTICO_RESP e CD_CONRE (dados de pessoa natural) não são lidos.
POLLS_COLS = ["CD_ELEICAO", "NM_ELEICAO", "SG_UF", "SG_UE", "NM_UE", "NR_PROTOCOLO_REGISTRO", "DT_REGISTRO",
              "ST_PESQUISA_PROPRIA", "NR_CNPJ_EMPRESA", "NM_EMPRESA", "NM_EMPRESA_FANTASIA", "DS_CARGO",
              "DT_INICIO_PESQUISA", "DT_FIM_PESQUISA", "DT_DIVULGACAO", "QT_ENTREVISTADO", "VR_PESQUISA",
              "DS_METODOLOGIA_PESQUISA", "DS_PLANO_AMOSTRAL", "DS_DADO_MUNICIPIO"]


def load_polls(conn, res, path, *, chunk_rows, force=False):
    member = _member_by_suffix(path, "pesquisa_eleitoral_2026_BRASIL.csv")

    def body(conn, run, t):
        with conn.cursor() as cur:
            dup = _one(cur, f"SELECT count(*) - count(DISTINCT nr_protocolo_registro) FROM staging.{t}")
            cur.execute("DELETE FROM polls.registered_poll")
            cur.execute(f"""
                INSERT INTO polls.registered_poll (nr_protocolo_registro, cd_eleicao, nm_eleicao, sg_uf, sg_ue, nm_ue,
                    dt_registro, st_pesquisa_propria, nr_cnpj_empresa, nm_empresa, nm_empresa_fantasia, ds_cargo,
                    dt_inicio_pesquisa, dt_fim_pesquisa, dt_divulgacao, qt_entrevistado, vr_pesquisa,
                    ds_metodologia_pesquisa, ds_plano_amostral, ds_dado_municipio, source_import_id)
                SELECT DISTINCT ON (btrim(nr_protocolo_registro)) btrim(nr_protocolo_registro), staging.nn(cd_eleicao),
                       staging.nn(nm_eleicao), staging.nn(sg_uf), staging.nn(sg_ue), staging.nn(nm_ue),
                       staging.nn(dt_registro)::timestamp, staging.nn(st_pesquisa_propria), staging.nn(nr_cnpj_empresa),
                       staging.nn(nm_empresa), staging.nn(nm_empresa_fantasia), staging.nn(ds_cargo),
                       staging.nn(dt_inicio_pesquisa)::timestamp::date, staging.nn(dt_fim_pesquisa)::timestamp::date,
                       staging.nn(dt_divulgacao)::timestamp::date,
                       CASE WHEN btrim(qt_entrevistado) ~ '^[0-9]+$' THEN btrim(qt_entrevistado)::integer END,
                       CASE WHEN replace(btrim(vr_pesquisa), ',', '.') ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN replace(btrim(vr_pesquisa), ',', '.')::numeric END,
                       staging.nn(ds_metodologia_pesquisa), staging.nn(ds_plano_amostral),
                       staging.nn(ds_dado_municipio), %s
                FROM staging.{t}
                ORDER BY btrim(nr_protocolo_registro), staging.nn(dt_registro) DESC""", (run.id,))
            loaded = cur.rowcount
            staged = _one(cur, f"SELECT count(*) FROM staging.{t}")
            validation = {"rows": staged, "duplicated_protocol_rows": dup, "polls": loaded}
            runs.publish(cur, run, "pesquisas", None, staged, loaded, validation)
        return validation

    return run_import(conn, res, path, member, "polls:BRASIL", body, chunk_rows=chunk_rows, columns=POLLS_COLS,
                      force=force)


# ---------------------------------------------------------------- Geometrias IBGE
def _file_member(path: Path) -> Member:
    data = path.read_bytes()
    return Member(path.name, f"{zlib.crc32(data) & 0xFFFFFFFF:08x}", len(data), len(data))


def load_geometry(conn, res, path, level: str, *, force=False):
    member = _file_member(path)

    def body(conn, run, _t):
        doc = json.loads(path.read_text(encoding="utf-8"))
        feats = doc["features"]
        with conn.cursor() as cur:
            if level == "municipio":
                cur.execute("DELETE FROM core.municipality_geometry")
                cur.executemany(
                    """INSERT INTO core.municipality_geometry (cd_municipio_ibge, sg_uf, geom, source_import_id)
                       SELECT %(cd)s, s.sg_uf,
                              ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%(g)s), 4326)), 3)),
                              %(run)s
                       FROM core.state s WHERE s.cd_uf_ibge = left(%(cd)s, 2)""",
                    [{"cd": f["properties"]["codarea"], "g": json.dumps(f["geometry"]), "run": run.id} for f in feats])
                loaded = _one(cur, "SELECT count(*) FROM core.municipality_geometry")
                no_geom = _one(cur, """SELECT count(*) FROM core.municipality m LEFT JOIN core.municipality_geometry g
                           USING (cd_municipio_ibge) WHERE NOT m.is_exterior AND g.cd_municipio_ibge IS NULL""")
                no_mun = _one(cur, """SELECT count(*) FROM core.municipality_geometry g LEFT JOIN core.municipality m
                           USING (cd_municipio_ibge) WHERE m.cd_municipio_tse IS NULL""")
                validation = {"features": len(feats), "loaded": loaded, "municipalities_without_geometry": no_geom,
                              "geometries_without_municipality": no_mun}
            else:
                cur.execute("DELETE FROM core.state_geometry")
                cur.executemany(
                    """INSERT INTO core.state_geometry (cd_uf_ibge, geom)
                       VALUES (%(cd)s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%(g)s), 4326)))""",
                    [{"cd": f["properties"]["codarea"], "g": json.dumps(f["geometry"])} for f in feats])
                loaded = _one(cur, "SELECT count(*) FROM core.state_geometry")
                validation = {"features": len(feats), "loaded": loaded}
            invalid = _one(cur, "SELECT count(*) FROM core.municipality_geometry WHERE NOT ST_IsValid(geom)") \
                if level == "municipio" else 0
            validation["invalid_geometries"] = invalid
            runs.publish(cur, run, f"geo_{level}", None, len(feats), loaded, validation)
        return validation

    return run_import(conn, res, path, member, f"geo:{level}", body, chunk_rows=0, columns=None, force=force)
