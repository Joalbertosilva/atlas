"""Resultados: denominadores explícitos; agregados oficiais (munzona) — nunca somados às seções."""
import csv
import io

from flask import Response
from flask_smorest import Blueprint

from ..db import fetch_all, fetch_one
from ..errors import ApiError
from ..schemas import CompareArgs, MunicipalityResultsArgs, RankingArgs, ScopeArgs
from ..scope import (NO_DATA_COLOR, TIE_COLOR, contest_colors, contest_scope, coverage_meta, envelope, paging,
                     resolve_contest, source_meta)

blp = Blueprint("results", __name__, url_prefix="/api/results", description="Resultados eleitorais")
MUNZONA_KINDS = ("munzona_cand", "munzona_detalhe", "munzona_partido")


def _pct(num, den):
    return None if not den else round(100.0 * float(num) / float(den), 4)


def _turnout(c: dict) -> dict | None:
    if c["municipio"]:
        return fetch_one("SELECT * FROM agg.turnout_municipality WHERE contest_id = :c AND cd_municipio_tse = :m",
                         c=c["id"], m=c["municipio"])
    cols = """sum(qt_aptos) qt_aptos, sum(qt_comparecimento) qt_comparecimento, sum(qt_abstencoes) qt_abstencoes,
              sum(qt_votos) qt_votos, sum(qt_total_votos_validos) qt_total_votos_validos,
              sum(qt_votos_nominais_validos) qt_votos_nominais_validos,
              sum(qt_total_votos_leg_validos) qt_total_votos_leg_validos, sum(qt_votos_brancos) qt_votos_brancos,
              sum(qt_total_votos_nulos) qt_total_votos_nulos, sum(qt_total_votos_anul_subjud) qt_total_votos_anul_subjud,
              sum(qt_total_votos_anulados) qt_total_votos_anulados, sum(qt_total_secoes) qt_total_secoes,
              sum(qt_eleitores_secoes_nao_instaladas) qt_eleitores_secoes_nao_instaladas,
              max(dt_ultima_totalizacao) dt_ultima_totalizacao, count(*) n"""
    row = fetch_one(f"SELECT {cols} FROM agg.turnout_state WHERE contest_id = :c AND (CAST(:uf AS text) IS NULL OR sg_uf = :uf)",
                    c=c["id"], uf=c["uf"])
    return None if not row or not row["n"] else row


def _summary_obj(t: dict | None) -> dict | None:
    if not t:
        return None
    out = {k: (int(v) if isinstance(v, (int, float)) or hasattr(v, "as_integer_ratio") else v)
           for k, v in t.items() if k.startswith("qt_")}
    out["pct_comparecimento"] = _pct(t["qt_comparecimento"], t["qt_aptos"])
    out["pct_abstencao"] = _pct(t["qt_abstencoes"], t["qt_aptos"])
    out["pct_brancos"] = _pct(t["qt_votos_brancos"], t["qt_votos"])
    out["pct_nulos"] = _pct(t["qt_total_votos_nulos"], t["qt_votos"])
    out["dt_ultima_totalizacao"] = t["dt_ultima_totalizacao"].isoformat() if t.get("dt_ultima_totalizacao") else None
    return out


def _meta(c: dict, extra: dict | None = None, notes: list[str] | None = None) -> dict:
    src = source_meta(c["sg_ue"], MUNZONA_KINDS)
    n = list(notes or [])
    if c["cd_cargo"] == "5":
        n.append("Senador 2026: cada eleitor pôde escolher até 2 candidaturas; total de votos ≠ número de votantes.")
    return {"scope": contest_scope(c), "source": src, "coverage": coverage_meta(src, n), **(extra or {})}


@blp.route("/summary")
@blp.arguments(ScopeArgs, location="query")
def summary(args):
    """Totais do recorte: aptos, comparecimento, abstenção, válidos, brancos, nulos."""
    c = resolve_contest(args["cargo"], args["turno"], args["uf"], args["municipio"])
    data = _summary_obj(_turnout(c))
    if data is None:
        raise ApiError(404, "Sem dados de comparecimento publicados para este recorte.")
    data["choices_per_voter"] = c["choices_per_voter"]
    data["exterior"] = None
    if c["cd_cargo"] == "1" and not c["uf"] and not c["municipio"]:
        ext = dict(c, uf="ZZ")
        data["exterior"] = _summary_obj(_turnout(ext))
    meta = _meta(c, {"denominators": {
        "pct_comparecimento": "qt_comparecimento / qt_aptos",
        "pct_abstencao": "qt_abstencoes / qt_aptos",
        "pct_brancos": "qt_votos_brancos / qt_votos",
        "pct_nulos": "qt_total_votos_nulos / qt_votos",
        "nota": "qt_aptos inclui eleitores de seções não instaladas (qt_eleitores_secoes_nao_instaladas)."}})
    return envelope(data, meta)


def _ranking_rows(c: dict, kind: str) -> list[dict]:
    if c["municipio"]:
        src, filt = "agg.result_municipality", "r.cd_municipio_tse = :m"
    else:
        src, filt = "agg.result_state", "(CAST(:uf AS text) IS NULL OR r.sg_uf = :uf)"
    kinds = ["candidatura"] if kind == "candidatura" else ["candidatura", "legenda", "branco", "nulo"]
    rows = fetch_all(f"""
        WITH r AS (
            SELECT r.option_id, sum(r.qt_votos) AS qt_votos, sum(r.qt_votos_validos) AS qt_votos_validos
            FROM {src} r WHERE r.contest_id = :c AND {filt} GROUP BY r.option_id)
        SELECT o.id AS option_id, o.kind, o.nr_votavel, o.label, o.candidacy_id, cd.nm_candidato,
               coalesce(cd.sg_partido, p.sg_partido) AS sg_partido, cd.sg_federacao,
               r.qt_votos, r.qt_votos_validos, cr.ds_sit_tot_turno, cr.nm_tipo_destinacao_votos,
               CASE WHEN o.kind = 'candidatura'
                    THEN rank() OVER (PARTITION BY (o.kind = 'candidatura') ORDER BY r.qt_votos_validos DESC) END AS rank
        FROM r JOIN core.vote_option o ON o.id = r.option_id
        LEFT JOIN core.candidacy cd ON cd.id = o.candidacy_id
        LEFT JOIN core.candidacy_round cr ON cr.candidacy_id = o.candidacy_id AND cr.nr_turno = :turno
        LEFT JOIN LATERAL (SELECT sg_partido FROM core.candidacy x WHERE o.kind = 'legenda'
                           AND x.cd_eleicao = o.cd_eleicao AND x.nr_partido = o.nr_partido LIMIT 1) p ON true
        WHERE o.kind = ANY(:kinds)
        ORDER BY (o.kind <> 'candidatura'), r.qt_votos_validos DESC, r.qt_votos DESC, o.nr_votavel""",
        c=c["id"], m=c["municipio"], uf=c["uf"], turno=c["nr_turno"], kinds=kinds)
    return rows


@blp.route("/ranking")
@blp.arguments(RankingArgs, location="query")
def ranking(args):
    """Ranking por disputa e recorte. `pct_validos` = votos válidos da opção / total de válidos do recorte."""
    c = resolve_contest(args["cargo"], args["turno"], args["uf"], args["municipio"])
    t = _turnout(c)
    validos = t["qt_total_votos_validos"] if t else None
    nominais = t["qt_votos_nominais_validos"] if t else None
    colors = contest_colors(c["id"])
    rows = _ranking_rows(c, args["kind"])
    prop = c["system"] == "proporcional"
    for r in rows:
        r["qt_votos"], r["qt_votos_validos"] = int(r["qt_votos"]), int(r["qt_votos_validos"])
        r["pct_validos"] = _pct(r["qt_votos_validos"], validos) if r["kind"] in ("candidatura", "legenda") else None
        r["pct_nominais"] = _pct(r["qt_votos_validos"], nominais) if prop and r["kind"] == "candidatura" else None
        r["color"] = colors.get(r["option_id"], NO_DATA_COLOR if r["kind"] != "candidatura" else "#94a3b8")
    if args["format"] == "csv":
        return _csv(rows, ["rank", "nr_votavel", "label", "nm_candidato", "sg_partido", "kind", "qt_votos",
                           "qt_votos_validos", "pct_validos", "pct_nominais", "ds_sit_tot_turno",
                           "nm_tipo_destinacao_votos"], f"ranking_cargo{c['cd_cargo']}_{c['uf'] or 'BR'}"
                                                         f"{'_' + c['municipio'] if c['municipio'] else ''}.csv")
    total = len(rows)
    start = (args["page"] - 1) * args["page_size"]
    meta = _meta(c, {
        "pagination": paging(args["page"], args["page_size"], total),
        "denominators": {"pct_validos": "qt_total_votos_validos do recorte (nominais válidos + legenda válidos)",
                         "pct_nominais": "qt_votos_nominais_validos do recorte (apenas cargos proporcionais)",
                         "qt_total_votos_validos": validos, "qt_votos_nominais_validos": nominais}},
        ["Situação (eleito, 2º turno, suplente...) vem do campo oficial DS_SIT_TOT_TURNO; o ranking não define eleitos."])
    return envelope(rows[start:start + args["page_size"]], meta)


def _csv(rows: list[dict], cols: list[str], filename: str) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(cols)
    for r in rows:
        # prefixo evita injeção de fórmula em planilhas
        w.writerow([("'" + v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v
                    for v in (r.get(c) for c in cols)])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@blp.route("/municipalities")
@blp.arguments(MunicipalityResultsArgs, location="query")
def municipalities(args):
    """Uma linha por município (sem geometria): líder com empate/margem, ou desempenho de uma candidatura."""
    c = resolve_contest(args["cargo"], args["turno"], args["uf"], None)
    colors = contest_colors(c["id"])
    if args["mode"] == "candidate":
        opt = fetch_one("""SELECT o.id, o.label FROM core.vote_option o JOIN core.contest c ON c.id = :c
                           WHERE o.id = :o AND o.cd_eleicao = c.cd_eleicao AND o.cd_cargo = c.cd_cargo
                           AND o.sg_ue = c.sg_ue AND o.kind = 'candidatura'""", c=c["id"], o=args["option_id"])
        if opt is None:
            raise ApiError(400, "option_id não pertence a esta disputa.")
        rows = fetch_all("""
            SELECT m.cd_municipio_tse, m.cd_municipio_ibge, m.nm_municipio, m.sg_uf, m.is_exterior,
                   coalesce(r.qt_votos_validos, 0) AS qt_votos_validos, t.qt_total_votos_validos,
                   (t.contest_id IS NOT NULL) AS has_data
            FROM core.municipality m
            LEFT JOIN agg.turnout_municipality t ON t.contest_id = :c AND t.cd_municipio_tse = m.cd_municipio_tse
            LEFT JOIN agg.result_municipality r ON r.contest_id = :c AND r.cd_municipio_tse = m.cd_municipio_tse
                 AND r.option_id = :o
            WHERE (CAST(:uf AS text) IS NULL OR m.sg_uf = :uf) AND (CAST(:uf AS text) IS NOT NULL OR :br)
            ORDER BY m.sg_uf, m.nm_municipio""", c=c["id"], o=args["option_id"], uf=c["uf"], br=c["sg_ue"] == "BR")
        vals = []
        for r in rows:
            r["qt_total_votos_validos"] = int(r["qt_total_votos_validos"]) if r["has_data"] else None
            r["qt_votos_validos"] = int(r["qt_votos_validos"]) if r["has_data"] else None
            r["pct_validos"] = _pct(r["qt_votos_validos"], r["qt_total_votos_validos"]) if r["has_data"] else None
            del r["has_data"]
            if r["pct_validos"] is not None:
                vals.append(r["pct_validos"])
        hi = max(vals) if vals else 0
        bands = [{"min": round(hi * i / 5, 2), "max": round(hi * (i + 1) / 5, 2)} for i in range(5)]
        meta = _meta(c, {"legend": {"type": "sequential", "option_id": opt["id"], "label": opt["label"],
                                    "color": colors.get(opt["id"]), "bands": bands, "no_data_color": NO_DATA_COLOR},
                         "denominators": {"pct_validos": "votos válidos da candidatura / válidos do município"}})
        if args["format"] == "csv":
            return _csv(rows, ["cd_municipio_tse", "cd_municipio_ibge", "nm_municipio", "sg_uf", "qt_votos_validos",
                               "qt_total_votos_validos", "pct_validos"], f"municipios_opcao{opt['id']}.csv")
        return envelope(rows, meta)

    rows = fetch_all("""
        WITH r AS (
            SELECT rm.cd_municipio_tse, rm.option_id, rm.qt_votos_validos, o.label, o.nr_votavel,
                   rank() OVER (PARTITION BY rm.cd_municipio_tse ORDER BY rm.qt_votos_validos DESC) AS rk,
                   row_number() OVER (PARTITION BY rm.cd_municipio_tse
                                      ORDER BY rm.qt_votos_validos DESC, o.nr_votavel) AS rn
            FROM agg.result_municipality rm
            JOIN core.vote_option o ON o.id = rm.option_id AND o.kind = 'candidatura'
            WHERE rm.contest_id = :c AND (CAST(:uf AS text) IS NULL OR rm.sg_uf = :uf)),
        top AS (
            SELECT cd_municipio_tse,
                   max(option_id) FILTER (WHERE rn = 1) AS o1, max(label) FILTER (WHERE rn = 1) AS l1,
                   max(qt_votos_validos) FILTER (WHERE rn = 1) AS v1,
                   max(option_id) FILTER (WHERE rn = 2) AS o2, max(label) FILTER (WHERE rn = 2) AS l2,
                   max(qt_votos_validos) FILTER (WHERE rn = 2) AS v2,
                   array_agg(option_id ORDER BY nr_votavel) FILTER (WHERE rk = 1) AS tied
            FROM r WHERE rn <= 2 OR rk = 1 GROUP BY cd_municipio_tse)
        SELECT m.cd_municipio_tse, m.cd_municipio_ibge, m.nm_municipio, m.sg_uf, m.is_exterior,
               t.qt_total_votos_validos, top.*
        FROM core.municipality m
        LEFT JOIN agg.turnout_municipality t ON t.contest_id = :c AND t.cd_municipio_tse = m.cd_municipio_tse
        LEFT JOIN top ON top.cd_municipio_tse = m.cd_municipio_tse
        WHERE (CAST(:uf AS text) IS NULL OR m.sg_uf = :uf) AND (CAST(:uf AS text) IS NOT NULL OR :br)
        ORDER BY m.sg_uf, m.nm_municipio""", c=c["id"], uf=c["uf"], br=c["sg_ue"] == "BR")
    out, legend = [], {}
    for r in rows:
        validos = int(r["qt_total_votos_validos"]) if r["qt_total_votos_validos"] is not None else None
        has = r["o1"] is not None and r["v1"] and r["v1"] > 0
        tied = [int(x) for x in (r["tied"] or [])] if has else []
        tie = len(tied) > 1
        leader = {"option_id": r["o1"], "label": r["l1"], "color": TIE_COLOR if tie else colors.get(r["o1"]),
                  "qt_votos_validos": int(r["v1"]), "pct_validos": _pct(r["v1"], validos)} if has else None
        second = {"option_id": r["o2"], "label": r["l2"], "color": colors.get(r["o2"]),
                  "qt_votos_validos": int(r["v2"]), "pct_validos": _pct(r["v2"], validos)} \
            if has and r["o2"] is not None else None
        margin = int(r["v1"]) - int(r["v2"] or 0) if has and r["o2"] is not None else None
        out.append({"cd_municipio_tse": r["cd_municipio_tse"], "cd_municipio_ibge": r["cd_municipio_ibge"],
                    "nm_municipio": r["nm_municipio"], "sg_uf": r["sg_uf"], "is_exterior": r["is_exterior"],
                    "leader": leader, "second": second, "tie": tie, "tied_option_ids": tied if tie else [],
                    "margin_votes": margin, "margin_pp": _pct(margin, validos) if margin is not None else None,
                    "qt_total_votos_validos": validos})
        key = "empate" if tie else (r["o1"] if has else "sem_dados")
        if key not in legend:
            legend[key] = {"option_id": None if key in ("empate", "sem_dados") else r["o1"],
                           "label": "Empate" if tie else (r["l1"] if has else "Sem dados"),
                           "color": TIE_COLOR if tie else (colors.get(r["o1"]) if has else NO_DATA_COLOR),
                           "municipios": 0}
        legend[key]["municipios"] += 1
    if args["format"] == "csv":
        flat = [{**{k: v for k, v in o.items() if k not in ("leader", "second", "tied_option_ids")},
                 "lider": o["leader"]["label"] if o["leader"] else None,
                 "lider_votos_validos": o["leader"]["qt_votos_validos"] if o["leader"] else None,
                 "lider_pct_validos": o["leader"]["pct_validos"] if o["leader"] else None,
                 "segundo": o["second"]["label"] if o["second"] else None} for o in out]
        return _csv(flat, ["cd_municipio_tse", "cd_municipio_ibge", "nm_municipio", "sg_uf", "lider",
                           "lider_votos_validos", "lider_pct_validos", "segundo", "tie", "margin_votes", "margin_pp",
                           "qt_total_votos_validos"], f"lideres_cargo{c['cd_cargo']}_{c['uf'] or 'BR'}.csv")
    meta = _meta(c, {"legend": {"type": "categorical", "items": sorted(legend.values(), key=lambda x: -x["municipios"])},
                     "denominators": {"pct_validos": "válidos do município", "margin_pp":
                                      "(votos do 1º − votos do 2º) / válidos do município, em pontos percentuais"}},
                 ["Líder = maior número de votos válidos no município; empate quando há mais de uma candidatura com o "
                  "mesmo máximo. Exterior não aparece no mapa."])
    return envelope(out, meta)


@blp.route("/compare")
@blp.arguments(CompareArgs, location="query")
def compare(args):
    """Comparação de até 3 candidaturas da mesma disputa, por município."""
    c = resolve_contest(args["cargo"], args["turno"], args["uf"], None)
    ids = sorted({int(x) for x in args["option_ids"].split(",")})
    valid = fetch_all("""SELECT o.id FROM core.vote_option o JOIN core.contest c ON c.id = :c
                         WHERE o.id = ANY(:ids) AND o.kind = 'candidatura' AND o.cd_eleicao = c.cd_eleicao
                         AND o.cd_cargo = c.cd_cargo AND o.sg_ue = c.sg_ue""", c=c["id"], ids=ids)
    if len(valid) != len(ids):
        raise ApiError(400, "Todas as candidaturas devem pertencer à mesma disputa selecionada.")
    colors = contest_colors(c["id"])
    options = [r for r in _ranking_rows(c, "candidatura") if r["option_id"] in ids]
    t = _turnout(c)
    for r in options:
        r["qt_votos"], r["qt_votos_validos"] = int(r["qt_votos"]), int(r["qt_votos_validos"])
        r["pct_validos"] = _pct(r["qt_votos_validos"], t["qt_total_votos_validos"] if t else None)
        r["color"] = colors.get(r["option_id"])
    rows = fetch_all("""
        SELECT m.cd_municipio_tse, m.nm_municipio, m.sg_uf, t.qt_total_votos_validos,
               jsonb_object_agg(r.option_id, r.qt_votos_validos) FILTER (WHERE r.option_id IS NOT NULL) AS v
        FROM agg.turnout_municipality t
        JOIN core.municipality m ON m.cd_municipio_tse = t.cd_municipio_tse
        LEFT JOIN agg.result_municipality r ON r.contest_id = t.contest_id AND r.cd_municipio_tse = t.cd_municipio_tse
             AND r.option_id = ANY(:ids)
        WHERE t.contest_id = :c AND (CAST(:uf AS text) IS NULL OR t.sg_uf = :uf)
        GROUP BY 1, 2, 3, 4 ORDER BY 3, 2""", c=c["id"], ids=ids, uf=c["uf"])
    muns = []
    for r in rows:
        vt = int(r["qt_total_votos_validos"])
        vals = {str(i): {"qt_votos_validos": int((r["v"] or {}).get(str(i), 0)),
                         "pct_validos": _pct(int((r["v"] or {}).get(str(i), 0)), vt)} for i in ids}
        muns.append({"cd_municipio_tse": r["cd_municipio_tse"], "nm_municipio": r["nm_municipio"],
                     "sg_uf": r["sg_uf"], "qt_total_votos_validos": vt, "values": vals})
    return envelope({"options": options, "municipalities": muns}, _meta(c))
