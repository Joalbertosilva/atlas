"""Referências, cobertura, saúde e geometria."""
import json
import threading

from flask import Response, current_app
from flask_smorest import Blueprint

from ..db import fetch_all, scalar, set_statement_timeout
from ..schemas import CandidaciesArgs, GeometryArgs, MunicipalitiesArgs
from ..scope import envelope, paging

blp = Blueprint("meta", __name__, url_prefix="/api", description="Referências, cobertura e geometria")


def _as_geojson(raw):
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
       "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
UES = ["BR"] + UFS
EXPECTED = {
    "Referência TSE–IBGE": ["ref:municipio_tse_ibge"],
    "Malhas IBGE": ["geo:municipio", "geo:uf"],
    "Vagas": ["ref:consulta_vagas"],
    "Candidaturas (cadastro)": [f"cand:{u}" for u in UES],
    "Comparecimento/brancos/nulos por município e zona": [f"munzona_detalhe:{u}" for u in UES],
    "Votos por candidatura, município e zona": [f"munzona_cand:{u}" for u in UES],
    "Votos de legenda, município e zona": [f"munzona_partido:{u}" for u in UES],
    "Locais de votação e seções": [f"locais:{u}" for u in UFS + ["ZZ"]],
    "Votos por seção": [f"secao:{u}" for u in UES + ["ZZ"]],
    "Comparecimento por seção": [f"detalhe_secao:{u}" for u in UES + ["ZZ"]],
    "Pesquisas registradas": ["polls:BRASIL"],
}
_geom_cache: dict[tuple, bytes] = {}
_geom_lock = threading.Lock()


@blp.route("/health")
def health():
    db_ok = "ok"
    try:
        scalar("SELECT 1")
    except Exception:  # noqa: BLE001
        db_ok = "erro"
    sx = current_app.extensions["atlas_search"].ping()
    status = "ok" if db_ok == "ok" else "degradado"
    return envelope({"status": status, "database": db_ok, "searxng": "ok" if sx else "erro"},
                    status=200 if db_ok == "ok" else 503)


@blp.route("/coverage")
def coverage():
    pubs = {r["scope_key"]: r for r in fetch_all("""
        SELECT p.scope_key, p.rows_published, p.published_at, r.source_generated_at, r.member_name, r.validation
        FROM meta.publication p JOIN meta.import_run r ON r.id = p.import_run_id""")}
    fails = {r["scope_key"]: r["error"] for r in fetch_all("""
        SELECT DISTINCT ON (scope_key) scope_key, status, error FROM meta.import_run
        ORDER BY scope_key, id DESC""") if r["status"] == "failed"}
    groups, scopes, pending = [], [], []
    for label, keys in EXPECTED.items():
        done = [k for k in keys if k in pubs]
        groups.append({"group": label, "published": len(done), "expected": len(keys),
                       "status": "completo" if len(done) == len(keys) else ("parcial" if done else "pendente")})
        for k in keys:
            p = pubs.get(k)
            scopes.append({"group": label, "scope": k, "status": "publicado" if p else ("falhou" if k in fails else "pendente"),
                           "rows": p["rows_published"] if p else None,
                           "source_generated_at": p["source_generated_at"].isoformat() if p and p["source_generated_at"] else None,
                           "imported_at": p["published_at"].isoformat() if p else None,
                           "member": p["member_name"] if p else None,
                           "note": (p["validation"] or {}).get("note") if p else None,
                           "error": fails.get(k) if not p else None})
            if not p:
                pending.append(f"{label}: {k}" + (" (última tentativa falhou)" if k in fails else ""))
    recon = fetch_all("""
        WITH last AS (SELECT max(checked_at) t FROM meta.reconciliation)
        SELECT check_name, count(*) total, count(*) FILTER (WHERE ok) ok,
               (array_agg(scope ORDER BY scope) FILTER (WHERE NOT ok))[1:10] AS examples
        FROM meta.reconciliation, last WHERE checked_at >= last.t - interval '30 minutes'
        GROUP BY 1 ORDER BY 1""")
    summary = {
        "municipios_com_resultado": scalar("""SELECT count(DISTINCT cd_municipio_tse) FROM agg.turnout_municipality t
                                              JOIN core.contest c ON c.id = t.contest_id WHERE c.cd_cargo = '1'"""),
        "municipios_brasil": scalar("SELECT count(*) FROM core.municipality WHERE NOT is_exterior"),
        "cidades_exterior": scalar("SELECT count(*) FROM core.municipality WHERE is_exterior"),
        "municipios_sem_codigo_ibge": scalar("SELECT count(*) FROM core.municipality WHERE NOT is_exterior AND cd_municipio_ibge IS NULL"),
        "municipios_sem_geometria": [dict(r) for r in fetch_all("""
            SELECT m.cd_municipio_tse, m.nm_municipio, m.sg_uf, m.cd_municipio_ibge FROM core.municipality m
            LEFT JOIN core.municipality_geometry g USING (cd_municipio_ibge)
            WHERE NOT m.is_exterior AND g.cd_municipio_ibge IS NULL""")],
        "secoes_cadastradas": scalar("SELECT count(*) FROM core.section"),
        "secoes_por_vinculo": {r["link_status"]: r["n"] for r in fetch_all(
            "SELECT link_status, count(*) n FROM core.section GROUP BY 1")},
        "locais": scalar("SELECT count(*) FROM core.polling_place"),
        "locais_por_coordenada": {r["coord_status"]: r["n"] for r in fetch_all(
            "SELECT coord_status, count(*) n FROM core.polling_place GROUP BY 1")},
        "linhas_votos_secao": scalar("SELECT coalesce(sum(rows_published),0) FROM meta.publication WHERE kind = 'secao'"),
        "pesquisas_registradas": scalar("SELECT count(*) FROM polls.registered_poll"),
    }
    return envelope({"summary": summary, "groups": groups, "scopes": scopes, "reconciliation": recon,
                     "pending": pending})


@blp.route("/elections")
def elections():
    rows = fetch_all("""SELECT e.cd_eleicao, e.ds_eleicao, e.dt_eleicao, e.tp_abrangencia,
                               coalesce(array_agg(DISTINCT c.nr_turno) FILTER (WHERE c.id IS NOT NULL), '{}') AS turnos
                        FROM core.election e LEFT JOIN core.contest c USING (cd_eleicao)
                        GROUP BY 1 ORDER BY 1""")
    for r in rows:
        r["dt_eleicao"] = r["dt_eleicao"].isoformat()
    return envelope(rows)


@blp.route("/offices")
def offices():
    rows = fetch_all("""
        SELECT o.cd_cargo, o.ds_cargo, o.system, o.scope, min(c.cd_eleicao) AS cd_eleicao,
               coalesce(array_agg(DISTINCT c.nr_turno) FILTER (WHERE c.id IS NOT NULL), '{}') AS turnos,
               (SELECT jsonb_object_agg(s.sg_ue, s.qt_vaga) FROM core.seat s WHERE s.cd_cargo = o.cd_cargo) AS seats
        FROM core.office o LEFT JOIN core.contest c USING (cd_cargo)
        GROUP BY o.cd_cargo, o.ds_cargo, o.system, o.scope, o.sort_order ORDER BY o.sort_order""")
    return envelope(rows)


@blp.route("/states")
def states():
    return envelope(fetch_all("SELECT sg_uf, nm_uf, cd_uf_ibge, is_exterior FROM core.state ORDER BY is_exterior, nm_uf"))


@blp.route("/municipalities")
@blp.arguments(MunicipalitiesArgs, location="query")
def municipalities(args):
    params = dict(uf=args["uf"], q=args["q"], lim=args["page_size"], off=(args["page"] - 1) * args["page_size"])
    where = """(CAST(:uf AS text) IS NULL OR sg_uf = :uf)
               AND (CAST(:q AS text) IS NULL OR name_norm LIKE '%' || core.normalize_text(:q) || '%')"""
    total = scalar(f"SELECT count(*) FROM core.municipality WHERE {where}", **params)
    rows = fetch_all(f"""SELECT cd_municipio_tse, cd_municipio_ibge, nm_municipio, sg_uf, is_exterior
                         FROM core.municipality WHERE {where}
                         ORDER BY (CAST(:q AS text) IS NOT NULL AND name_norm LIKE core.normalize_text(:q) || '%') DESC,
                                  nm_municipio LIMIT :lim OFFSET :off""", **params)
    return envelope(rows, {"pagination": paging(args["page"], args["page_size"], total)})


@blp.route("/candidacies")
@blp.arguments(CandidaciesArgs, location="query")
def candidacies(args):
    params = dict(cargo=args["cargo"], uf=args["uf"], q=args["q"], lim=args["page_size"],
                  off=(args["page"] - 1) * args["page_size"])
    where = """(CAST(:cargo AS text) IS NULL OR c.cd_cargo = :cargo)
               AND (CAST(:uf AS text) IS NULL OR c.sg_ue = :uf OR (c.sg_ue = 'BR' AND :uf = 'BR'))
               AND (CAST(:q AS text) IS NULL OR c.name_norm LIKE '%' || core.normalize_text(:q) || '%')"""
    total = scalar(f"SELECT count(*) FROM core.candidacy c WHERE {where}", **params)
    rows = fetch_all(f"""
        SELECT c.id AS candidacy_id, c.sq_candidato, c.nr_candidato, c.nm_urna_candidato, c.nm_candidato, c.sg_partido,
               c.nm_partido, c.sg_federacao, c.nm_coligacao, c.cd_cargo, o.ds_cargo, c.sg_ue, c.ds_situacao_candidatura,
               coalesce((SELECT json_agg(json_build_object('nr_turno', r.nr_turno, 'ds_sit_tot_turno', r.ds_sit_tot_turno,
                         'nm_tipo_destinacao_votos', r.nm_tipo_destinacao_votos) ORDER BY r.nr_turno)
                         FROM core.candidacy_round r WHERE r.candidacy_id = c.id), '[]') AS rounds,
               (SELECT vo.id FROM core.vote_option vo WHERE vo.candidacy_id = c.id LIMIT 1) AS option_id
        FROM core.candidacy c JOIN core.office o USING (cd_cargo)
        WHERE {where} ORDER BY o.sort_order, c.sg_ue, c.nm_urna_candidato LIMIT :lim OFFSET :off""", **params)
    return envelope(rows, {"pagination": paging(args["page"], args["page_size"], total),
                           "notes": ["Dados pessoais como CPF, e-mail, título e data de nascimento não são importados."]})


@blp.route("/map/geometry")
@blp.arguments(GeometryArgs, location="query")
def geometry(args):
    """GeoJSON simplificado do IBGE (Malhas v3, qualidade mínima), sem resultados embutidos."""
    key = (args["level"], args["uf"])
    with _geom_lock:
        body = _geom_cache.get(key)
    if body is None:
        set_statement_timeout(120)
        if args["level"] == "municipio":
            rows = fetch_all(
                """SELECT g.cd_municipio_ibge, m.cd_municipio_tse, m.nm_municipio, g.sg_uf,
                          ST_AsGeoJSON(g.geom, 5) AS geom
                   FROM core.municipality_geometry g
                   LEFT JOIN core.municipality m USING (cd_municipio_ibge)
                   WHERE CAST(:uf AS text) IS NULL OR g.sg_uf = :uf""",
                uf=args["uf"],
            )
            features = []
            for row in rows:
                geom = _as_geojson(row["geom"])
                if not geom:
                    continue
                features.append({
                    "type": "Feature",
                    "id": row["cd_municipio_ibge"],
                    "geometry": geom,
                    "properties": {
                        "cd_municipio_ibge": row["cd_municipio_ibge"],
                        "cd_municipio_tse": row["cd_municipio_tse"],
                        "nm_municipio": row["nm_municipio"],
                        "sg_uf": row["sg_uf"],
                    },
                })
            fc = {"type": "FeatureCollection", "features": features}
        else:
            rows = fetch_all(
                """SELECT g.cd_uf_ibge, s.sg_uf, s.nm_uf, ST_AsGeoJSON(g.geom, 5) AS geom
                   FROM core.state_geometry g JOIN core.state s ON s.cd_uf_ibge = g.cd_uf_ibge
                   WHERE CAST(:uf AS text) IS NULL OR s.sg_uf = :uf""",
                uf=args["uf"],
            )
            features = []
            for row in rows:
                geom = _as_geojson(row["geom"])
                if not geom:
                    continue
                features.append({
                    "type": "Feature",
                    "id": row["cd_uf_ibge"],
                    "geometry": geom,
                    "properties": {
                        "cd_uf_ibge": row["cd_uf_ibge"],
                        "sg_uf": row["sg_uf"],
                        "nm_uf": row["nm_uf"],
                    },
                })
            fc = {"type": "FeatureCollection", "features": features}
        body = json.dumps(fc, separators=(",", ":"), ensure_ascii=False).encode()
        with _geom_lock:
            _geom_cache[key] = body
    return Response(body, mimetype="application/geo+json",
                    headers={"Cache-Control": "public, max-age=86400",
                             "X-Source": "IBGE API de Malhas v3 (qualidade minima)"})
