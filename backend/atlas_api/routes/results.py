"""Resultados: denominadores explícitos; agregados oficiais (munzona) — nunca somados às seções."""
import csv
import io

from flask import Response
from flask_smorest import Blueprint

from ..db import fetch_all, fetch_one
from ..errors import ApiError
from ..schemas import (CompareArgs, CrossCompareArgs, MunicipalityResultsArgs, PartyCompareArgs, RankingArgs, ScopeArgs,
                       UfLeadersArgs)
from ..scope import (NO_DATA_COLOR, TIE_COLOR, color_for_party, contest_colors, contest_scope, coverage_meta,
                     envelope, find_contest, paging, resolve_contest, source_meta)

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


def _ano(c_or_args) -> int:
    if isinstance(c_or_args, dict):
        return int(c_or_args.get("ano_eleicao") or c_or_args.get("ano") or 2026)
    return 2026


def _meta(c: dict, extra: dict | None = None, notes: list[str] | None = None) -> dict:
    src = source_meta(c["sg_ue"], MUNZONA_KINDS, _ano(c))
    n = list(notes or [])
    if c["cd_cargo"] == "5":
        if _ano(c) == 2026:
            n.append("Senador 2026: cada eleitor pôde escolher até 2 candidaturas; total de votos ≠ número de votantes.")
        else:
            n.append("Senador 2022: renovação de 1 vaga por UF; total de votos ≠ número de votantes.")
    return {"scope": contest_scope(c), "source": src, "coverage": coverage_meta(src, n), **(extra or {})}


@blp.route("/summary")
@blp.arguments(ScopeArgs, location="query")
def summary(args):
    """Totais do recorte: aptos, comparecimento, abstenção, válidos, brancos, nulos."""
    c = resolve_contest(args["cargo"], args["turno"], args["uf"], args["municipio"], args.get("ano", 2026))
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
               cd.sq_candidato, o.cd_eleicao, o.sg_ue,
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
    c = resolve_contest(args["cargo"], args["turno"], args["uf"], args["municipio"], args.get("ano", 2026))
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
        return _csv(rows, ["rank", "nr_votavel", "label", "nm_candidato", "sq_candidato", "cd_eleicao", "sg_ue",
                           "sg_partido", "kind", "qt_votos",
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


def _pack_leaders(rows: list[dict], colors: dict[int, str]) -> tuple[list[dict], dict]:
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
        out.append({"cd_municipio_tse": r["cd_municipio_tse"] or "",
                    "cd_municipio_ibge": r["cd_municipio_ibge"],
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
    return out, legend


@blp.route("/municipalities")
@blp.arguments(MunicipalityResultsArgs, location="query")
def municipalities(args):
    """Uma linha por município ou UF (sem geometria): líder com empate/margem, ou desempenho de uma candidatura."""
    c = resolve_contest(args["cargo"], args["turno"], args["uf"], None, args.get("ano", 2026))
    colors = contest_colors(c["id"])
    level = args.get("level") or "municipio"
    if args["mode"] == "candidate":
        opt = fetch_one("""SELECT o.id, o.label FROM core.vote_option o JOIN core.contest c ON c.id = :c
                           WHERE o.id = :o AND o.cd_eleicao = c.cd_eleicao AND o.cd_cargo = c.cd_cargo
                           AND o.sg_ue = c.sg_ue AND o.kind = 'candidatura'""", c=c["id"], o=args["option_id"])
        if opt is None:
            raise ApiError(400, "option_id não pertence a esta disputa.")
        if level == "uf":
            rows = fetch_all("""
                SELECT ''::text AS cd_municipio_tse, NULL::text AS cd_municipio_ibge, s.nm_uf AS nm_municipio,
                       s.sg_uf, s.is_exterior, coalesce(r.qt_votos_validos, 0) AS qt_votos_validos,
                       t.qt_total_votos_validos, (t.contest_id IS NOT NULL) AS has_data
                FROM core.state s
                LEFT JOIN agg.turnout_state t ON t.contest_id = :c AND t.sg_uf = s.sg_uf
                LEFT JOIN agg.result_state r ON r.contest_id = :c AND r.sg_uf = s.sg_uf AND r.option_id = :o
                WHERE s.sg_uf <> 'ZZ' AND (CAST(:uf AS text) IS NULL OR s.sg_uf = :uf)
                ORDER BY s.sg_uf""", c=c["id"], o=args["option_id"], uf=c["uf"])
        else:
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
        grain = "da UF" if level == "uf" else "do município"
        meta = _meta(c, {"legend": {"type": "sequential", "option_id": opt["id"], "label": opt["label"],
                                    "color": colors.get(opt["id"]), "bands": bands, "no_data_color": NO_DATA_COLOR},
                         "denominators": {"pct_validos": f"votos válidos da candidatura / válidos {grain}"}})
        if args["format"] == "csv":
            return _csv(rows, ["cd_municipio_tse", "cd_municipio_ibge", "nm_municipio", "sg_uf", "qt_votos_validos",
                               "qt_total_votos_validos", "pct_validos"], f"municipios_opcao{opt['id']}.csv")
        return envelope(rows, meta)

    if level == "uf":
        rows = fetch_all("""
            WITH r AS (
                SELECT rs.sg_uf, rs.option_id, rs.qt_votos_validos, o.label, o.nr_votavel,
                       rank() OVER (PARTITION BY rs.sg_uf ORDER BY rs.qt_votos_validos DESC) AS rk,
                       row_number() OVER (PARTITION BY rs.sg_uf
                                          ORDER BY rs.qt_votos_validos DESC, o.nr_votavel) AS rn
                FROM agg.result_state rs
                JOIN core.vote_option o ON o.id = rs.option_id AND o.kind = 'candidatura'
                WHERE rs.contest_id = :c AND rs.sg_uf <> 'ZZ'
                  AND (CAST(:uf AS text) IS NULL OR rs.sg_uf = :uf)),
            top AS (
                SELECT sg_uf,
                       max(option_id) FILTER (WHERE rn = 1) AS o1, max(label) FILTER (WHERE rn = 1) AS l1,
                       max(qt_votos_validos) FILTER (WHERE rn = 1) AS v1,
                       max(option_id) FILTER (WHERE rn = 2) AS o2, max(label) FILTER (WHERE rn = 2) AS l2,
                       max(qt_votos_validos) FILTER (WHERE rn = 2) AS v2,
                       array_agg(option_id ORDER BY nr_votavel) FILTER (WHERE rk = 1) AS tied
                FROM r WHERE rn <= 2 OR rk = 1 GROUP BY sg_uf)
            SELECT ''::text AS cd_municipio_tse, NULL::text AS cd_municipio_ibge, s.nm_uf AS nm_municipio,
                   s.sg_uf, s.is_exterior, t.qt_total_votos_validos, top.o1, top.l1, top.v1, top.o2, top.l2, top.v2,
                   top.tied
            FROM core.state s
            LEFT JOIN agg.turnout_state t ON t.contest_id = :c AND t.sg_uf = s.sg_uf
            LEFT JOIN top ON top.sg_uf = s.sg_uf
            WHERE s.sg_uf <> 'ZZ' AND (CAST(:uf AS text) IS NULL OR s.sg_uf = :uf)
            ORDER BY s.sg_uf""", c=c["id"], uf=c["uf"])
        grain_note = "Líder = maior número de votos válidos na UF (agg.result_state); empate quando há mais de uma candidatura com o mesmo máximo. Exterior (ZZ) não aparece no mapa."
        den_place = "da UF"
    else:
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
                   t.qt_total_votos_validos, top.o1, top.l1, top.v1, top.o2, top.l2, top.v2, top.tied
            FROM core.municipality m
            LEFT JOIN agg.turnout_municipality t ON t.contest_id = :c AND t.cd_municipio_tse = m.cd_municipio_tse
            LEFT JOIN top ON top.cd_municipio_tse = m.cd_municipio_tse
            WHERE (CAST(:uf AS text) IS NULL OR m.sg_uf = :uf) AND (CAST(:uf AS text) IS NOT NULL OR :br)
            ORDER BY m.sg_uf, m.nm_municipio""", c=c["id"], uf=c["uf"], br=c["sg_ue"] == "BR")
        grain_note = ("Líder = maior número de votos válidos no município; empate quando há mais de uma candidatura com o "
                      "mesmo máximo. Exterior não aparece no mapa.")
        den_place = "do município"
    out, legend = _pack_leaders(rows, colors)
    if args["format"] == "csv":
        flat = [{**{k: v for k, v in o.items() if k not in ("leader", "second", "tied_option_ids")},
                 "lider": o["leader"]["label"] if o["leader"] else None,
                 "lider_votos_validos": o["leader"]["qt_votos_validos"] if o["leader"] else None,
                 "lider_pct_validos": o["leader"]["pct_validos"] if o["leader"] else None,
                 "segundo": o["second"]["label"] if o["second"] else None} for o in out]
        return _csv(flat, ["cd_municipio_tse", "cd_municipio_ibge", "nm_municipio", "sg_uf", "lider",
                           "lider_votos_validos", "lider_pct_validos", "segundo", "tie", "margin_votes", "margin_pp",
                           "qt_total_votos_validos"], f"lideres_{level}_cargo{c['cd_cargo']}_{c['uf'] or 'BR'}.csv")
    meta = _meta(c, {"legend": {"type": "categorical", "items": sorted(legend.values(), key=lambda x: -x["municipios"])},
                     "denominators": {"pct_validos": f"válidos {den_place}", "margin_pp":
                                      f"(votos do 1º − votos do 2º) / válidos {den_place}, em pontos percentuais"}},
                 [grain_note])
    return envelope(out, meta)


@blp.route("/uf-leaders")
@blp.arguments(UfLeadersArgs, location="query")
def uf_leaders(args):
    """Uma linha por UF: quem teve mais votos válidos na disputa estadual daquele cargo. Não define eleito."""
    cargo, turno, ano = args["cargo"], args["turno"], args.get("ano", 2026)
    if cargo == "1":
        raise ApiError(400, "Presidente não tem disputa por UF: use /results/municipalities?level=uf.")
    rows = fetch_all("""
        WITH ranked AS (
            SELECT c.sg_ue AS sg_uf, o.id AS option_id, o.label, o.nr_votavel, o.cd_eleicao, o.sg_ue,
                   cd.sq_candidato, cd.sg_partido, cr.ds_sit_tot_turno, r.qt_votos_validos,
                   t.qt_total_votos_validos,
                   rank() OVER (PARTITION BY c.id ORDER BY r.qt_votos_validos DESC) AS rk,
                   row_number() OVER (PARTITION BY c.id ORDER BY r.qt_votos_validos DESC, o.nr_votavel) AS rn
            FROM core.contest c
            JOIN core.election e ON e.cd_eleicao = c.cd_eleicao
            JOIN agg.result_state r ON r.contest_id = c.id AND r.sg_uf = c.sg_ue
            JOIN core.vote_option o ON o.id = r.option_id AND o.kind = 'candidatura'
            LEFT JOIN core.candidacy cd ON cd.id = o.candidacy_id
            LEFT JOIN core.candidacy_round cr ON cr.candidacy_id = o.candidacy_id AND cr.nr_turno = c.nr_turno
            LEFT JOIN agg.turnout_state t ON t.contest_id = c.id AND t.sg_uf = c.sg_ue
            WHERE c.cd_cargo = :cargo AND c.nr_turno = :turno AND e.ano_eleicao = :ano
              AND c.sg_ue NOT IN ('BR', 'ZZ')),
        top AS (
            SELECT sg_uf,
                   max(option_id) FILTER (WHERE rn = 1) AS o1, max(label) FILTER (WHERE rn = 1) AS l1,
                   max(qt_votos_validos) FILTER (WHERE rn = 1) AS v1,
                   max(option_id) FILTER (WHERE rn = 2) AS o2, max(label) FILTER (WHERE rn = 2) AS l2,
                   max(qt_votos_validos) FILTER (WHERE rn = 2) AS v2,
                   max(sq_candidato) FILTER (WHERE rn = 1) AS sq1,
                   max(cd_eleicao) FILTER (WHERE rn = 1) AS ele1,
                   max(sg_ue) FILTER (WHERE rn = 1) AS ue1,
                   max(sg_partido) FILTER (WHERE rn = 1) AS part1,
                   max(nr_votavel) FILTER (WHERE rn = 1) AS nr1,
                   max(sg_partido) FILTER (WHERE rn = 2) AS part2,
                   max(nr_votavel) FILTER (WHERE rn = 2) AS nr2,
                   max(ds_sit_tot_turno) FILTER (WHERE rn = 1) AS sit1,
                   max(qt_total_votos_validos) FILTER (WHERE rn = 1) AS validos,
                   array_agg(option_id ORDER BY nr_votavel) FILTER (WHERE rk = 1) AS tied
            FROM ranked WHERE rn <= 2 OR rk = 1 GROUP BY sg_uf)
        SELECT s.sg_uf, s.nm_uf, s.is_exterior, top.o1, top.l1, top.v1, top.o2, top.l2, top.v2,
               top.sq1, top.ele1, top.ue1, top.part1, top.nr1, top.part2, top.nr2, top.sit1, top.validos, top.tied
        FROM core.state s
        LEFT JOIN top ON top.sg_uf = s.sg_uf
        WHERE s.sg_uf <> 'ZZ'
        ORDER BY s.sg_uf""", cargo=cargo, turno=turno, ano=ano)
    packed = []
    for r in rows:
        validos = int(r["validos"]) if r["validos"] is not None else None
        has = r["o1"] is not None and r["v1"] and r["v1"] > 0
        tied = [int(x) for x in (r["tied"] or [])] if has else []
        tie = len(tied) > 1
        leader = {
            "option_id": r["o1"], "label": r["l1"], "sg_partido": r["part1"],
            "color": TIE_COLOR if tie else color_for_party(r["part1"], r["nr1"]),
            "qt_votos_validos": int(r["v1"]), "pct_validos": _pct(r["v1"], validos),
            "sq_candidato": r["sq1"], "cd_eleicao": r["ele1"], "sg_ue": r["ue1"],
            "ds_sit_tot_turno": r["sit1"],
        } if has else None
        second = {"option_id": r["o2"], "label": r["l2"],
                  "color": color_for_party(r["part2"], r["nr2"]),
                  "qt_votos_validos": int(r["v2"]), "pct_validos": _pct(r["v2"], validos)} \
            if has and r["o2"] is not None else None
        packed.append({
            "cd_municipio_tse": "", "cd_municipio_ibge": None, "nm_municipio": r["nm_uf"],
            "sg_uf": r["sg_uf"], "is_exterior": r["is_exterior"],
            "leader": leader, "second": second, "tie": tie, "tied_option_ids": tied if tie else [],
            "margin_votes": (int(r["v1"]) - int(r["v2"] or 0)) if has and r["o2"] is not None else None,
            "margin_pp": _pct(int(r["v1"]) - int(r["v2"] or 0), validos) if has and r["o2"] is not None else None,
            "qt_total_votos_validos": validos,
        })
    legend: dict = {}
    for row in packed:
        if row["tie"]:
            key = "empate"
            legend.setdefault(key, {"option_id": None, "label": "Empate", "color": TIE_COLOR, "municipios": 0})
            legend[key]["municipios"] += 1
        elif row["leader"]:
            key = row["leader"]["option_id"]
            legend.setdefault(key, {"option_id": key, "label": row["leader"]["label"],
                                    "color": row["leader"]["color"], "municipios": 0})
            legend[key]["municipios"] += 1
        else:
            legend.setdefault("sem_dados", {"option_id": None, "label": "Sem dados",
                                            "color": NO_DATA_COLOR, "municipios": 0})
            legend["sem_dados"]["municipios"] += 1
    extra = {"legend": {"type": "categorical", "items": sorted(legend.values(), key=lambda x: -x["municipios"])},
             "denominators": {"pct_validos": "válidos da UF nesta disputa"}}
    notes = ["Cada cor é a candidatura com mais votos válidos naquela UF. Situação oficial (eleito) vem do TSE, não desta lista."]
    if cargo in ("6", "7", "8"):
        notes.append("Cargo proporcional: o mapa mostra só quem teve mais votos, não o conjunto de eleitos.")
    meta = {
        "scope": {"cd_cargo": cargo, "nr_turno": turno, "ano_eleicao": ano, "sg_uf": None, "sg_ue": None},
        "coverage": {"notes": notes},
        **extra,
    }
    return envelope(packed, meta)


@blp.route("/compare")
@blp.arguments(CompareArgs, location="query")
def compare(args):
    """Comparação de até 3 candidaturas da mesma disputa, por município."""
    c = resolve_contest(args["cargo"], args["turno"], args["uf"], None, args.get("ano", 2026))
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


def _party_year(c: dict | None, metrica: str) -> dict:
    if c is None:
        return {"available": False, "reason": "recorte não publicado nesta base", "ano": None, "cd_eleicao": None,
                "choices_per_voter": None, "total_validos": None, "parties": {}, "places": [], "source": None}
    t = _turnout(c)
    total = int(t["qt_total_votos_validos"]) if t and t["qt_total_votos_validos"] is not None else None
    if c["municipio"]:
        src, filt, place_sql = "agg.result_municipality", "r.cd_municipio_tse = :m", None
    elif c["uf"]:
        src, filt, place_sql = "agg.result_municipality", "r.sg_uf = :uf", "municipio"
    else:
        src, filt, place_sql = "agg.result_state", "r.sg_uf <> 'ZZ'", "uf"
    kinds = ["candidatura"] if metrica == "nominais" else (["legenda"] if metrica == "legenda" else ["candidatura", "legenda"])
    rows = fetch_all(f"""
        WITH r AS (
            SELECT r.option_id, sum(r.qt_votos_validos) AS votos
            FROM {src} r WHERE r.contest_id = :c AND {filt} GROUP BY r.option_id)
        SELECT CASE WHEN o.kind = 'legenda' THEN o.nr_votavel
                    ELSE coalesce(cd.nr_partido, o.nr_partido) END AS nr_partido,
               min(coalesce(cd.sg_partido, o.nr_partido)) AS sg_partido,
               sum(r.votos) AS votos
        FROM r JOIN core.vote_option o ON o.id = r.option_id
        LEFT JOIN core.candidacy cd ON cd.id = o.candidacy_id
        WHERE o.kind = ANY(:kinds)
          AND CASE WHEN o.kind = 'legenda' THEN o.nr_votavel
                   ELSE coalesce(cd.nr_partido, o.nr_partido) END IS NOT NULL
        GROUP BY 1""", c=c["id"], m=c["municipio"], uf=c["uf"], kinds=kinds)
    parties = {}
    for r in rows:
        nr = str(r["nr_partido"])
        votos = int(r["votos"] or 0)
        parties[nr] = {"nr_partido": nr, "sg_partido": r["sg_partido"], "votos": votos,
                       "pct": _pct(votos, total)}
    places = []
    if place_sql == "uf":
        raw = fetch_all(f"""
            WITH r AS (
                SELECT r.sg_uf,
                       CASE WHEN o.kind = 'legenda' THEN o.nr_votavel
                            ELSE coalesce(cd.nr_partido, o.nr_partido) END AS nr_partido,
                       sum(r.qt_votos_validos) AS votos
                FROM agg.result_state r
                JOIN core.vote_option o ON o.id = r.option_id
                LEFT JOIN core.candidacy cd ON cd.id = o.candidacy_id
                WHERE r.contest_id = :c AND r.sg_uf <> 'ZZ' AND o.kind = ANY(:kinds)
                GROUP BY 1, 2)
            SELECT r.sg_uf AS place_id, r.sg_uf, NULL::text AS cd_municipio_tse, NULL::text AS cd_municipio_ibge,
                   s.nm_uf AS nome, r.nr_partido, r.votos, t.qt_total_votos_validos
            FROM r JOIN core.state s ON s.sg_uf = r.sg_uf
            JOIN agg.turnout_state t ON t.contest_id = :c AND t.sg_uf = r.sg_uf""",
                        c=c["id"], kinds=kinds)
    elif place_sql == "municipio":
        raw = fetch_all(f"""
            WITH r AS (
                SELECT r.cd_municipio_tse,
                       CASE WHEN o.kind = 'legenda' THEN o.nr_votavel
                            ELSE coalesce(cd.nr_partido, o.nr_partido) END AS nr_partido,
                       sum(r.qt_votos_validos) AS votos
                FROM agg.result_municipality r
                JOIN core.vote_option o ON o.id = r.option_id
                LEFT JOIN core.candidacy cd ON cd.id = o.candidacy_id
                WHERE r.contest_id = :c AND r.sg_uf = :uf AND o.kind = ANY(:kinds)
                GROUP BY 1, 2)
            SELECT r.cd_municipio_tse AS place_id, m.sg_uf, m.cd_municipio_tse, m.cd_municipio_ibge,
                   m.nm_municipio AS nome, r.nr_partido, r.votos, t.qt_total_votos_validos
            FROM r JOIN core.municipality m ON m.cd_municipio_tse = r.cd_municipio_tse
            JOIN agg.turnout_municipality t ON t.contest_id = :c AND t.cd_municipio_tse = r.cd_municipio_tse""",
                        c=c["id"], uf=c["uf"], kinds=kinds)
    else:
        raw = []
    by_place: dict[str, dict] = {}
    for r in raw:
        pid = str(r["place_id"])
        place = by_place.setdefault(pid, {
            "place_id": pid, "sg_uf": r["sg_uf"], "cd_municipio_tse": r["cd_municipio_tse"],
            "cd_municipio_ibge": r["cd_municipio_ibge"], "nome": r["nome"],
            "qt_total_votos_validos": int(r["qt_total_votos_validos"]) if r["qt_total_votos_validos"] is not None else None,
            "parties": {}})
        nr = str(r["nr_partido"]) if r["nr_partido"] is not None else None
        if not nr:
            continue
        votos = int(r["votos"] or 0)
        place["parties"][nr] = {"votos": votos, "pct": _pct(votos, place["qt_total_votos_validos"])}
    places = list(by_place.values())
    src = source_meta(c["sg_ue"], MUNZONA_KINDS, _ano(c))
    src.pop("_found", None)
    src.pop("_expected", None)
    return {"available": True, "reason": None, "ano": c.get("ano_eleicao"), "cd_eleicao": c["cd_eleicao"],
            "choices_per_voter": c["choices_per_voter"], "total_validos": total, "parties": parties,
            "places": places, "source": src}


@blp.route("/party-compare")
@blp.arguments(PartyCompareArgs, location="query")
def party_compare(args):
    """Desempenho partidário 2022 × 2026 no mesmo cargo, turno e território. Ausência ≠ zero."""
    c26 = resolve_contest(args["cargo"], args["turno"], args["uf"], args["municipio"], 2026)
    c22 = find_contest(args["cargo"], args["turno"], args["uf"], args["municipio"], 2022)
    y26 = _party_year(c26, args["metrica"])
    y22 = _party_year(c22, args["metrica"])
    nrs = sorted(set(y26["parties"]) | set(y22["parties"]), key=lambda n: (-(y26["parties"].get(n, {}).get("votos") or 0), n))
    if args["nr_partido"]:
        nrs = [n for n in nrs if n == args["nr_partido"]] or [args["nr_partido"]]
    parties = []
    for nr in nrs:
        a = y22["parties"].get(nr)
        b = y26["parties"].get(nr)
        v22 = a["votos"] if a else (None if not y22["available"] else 0)
        v26 = b["votos"] if b else (None if not y26["available"] else 0)
        p22 = a["pct"] if a else None
        p26 = b["pct"] if b else None
        if not y22["available"]:
            v22 = p22 = None
        if not y26["available"]:
            v26 = p26 = None
        delta_votos = (v26 - v22) if v22 is not None and v26 is not None else None
        delta_pp = round(p26 - p22, 4) if p22 is not None and p26 is not None else None
        delta_rel = round(100.0 * (v26 - v22) / v22, 4) if v22 not in (None, 0) and v26 is not None else None
        parties.append({
            "nr_partido": nr,
            "sg_partido_2022": a["sg_partido"] if a else None,
            "sg_partido_2026": b["sg_partido"] if b else None,
            "votos_2022": v22, "votos_2026": v26,
            "pct_2022": p22, "pct_2026": p26,
            "delta_votos": delta_votos, "delta_pp": delta_pp,
            "delta_rel_pct": delta_rel,
            "variacao_relativa": "indisponivel" if v22 in (None, 0) else "calculada",
        })
    selected = args["nr_partido"] or (parties[0]["nr_partido"] if parties else None)
    places22 = {p["place_id"]: p for p in y22["places"]}
    places26 = {p["place_id"]: p for p in y26["places"]}
    place_ids = sorted(set(places22) | set(places26))
    places = []
    for pid in place_ids:
        a, b = places22.get(pid), places26.get(pid)
        pa = (a["parties"].get(selected) if a and selected else None)
        pb = (b["parties"].get(selected) if b and selected else None)
        p22 = pa["pct"] if pa else None
        p26 = pb["pct"] if pb else None
        if not y22["available"] or a is None:
            p22 = None
        if not y26["available"] or b is None:
            p26 = None
        base = b or a
        places.append({
            "place_id": pid, "sg_uf": base["sg_uf"], "nome": base["nome"],
            "cd_municipio_tse": base.get("cd_municipio_tse"), "cd_municipio_ibge": base.get("cd_municipio_ibge"),
            "votos_2022": pa["votos"] if pa and y22["available"] else None,
            "votos_2026": pb["votos"] if pb and y26["available"] else None,
            "pct_2022": p22, "pct_2026": p26,
            "delta_pp": round(p26 - p22, 4) if p22 is not None and p26 is not None else None,
            "status": "comparavel" if p22 is not None and p26 is not None else (
                "so_2026" if p26 is not None else ("so_2022" if p22 is not None else "ausente")),
        })
    notes = [
        "Participação % = votos do partido (métrica escolhida) / qt_total_votos_validos do recorte.",
        "Ponto percentual (pp) é a diferença entre duas porcentagens. Variação relativa % = (votos 2026 − 2022) / votos 2022.",
        "Ausência de 2022 não é zero. Se a base anterior for 0, a variação relativa não é calculada.",
        "Não interpreta mudança de votos como transferência individual de eleitores.",
    ]
    if args["cargo"] == "5":
        notes.append("Senado: 2026 tem 2 escolhas por eleitor; 2022 renovou 1 vaga por UF. Totais de votos não são números de pessoas.")
    if not y22["available"]:
        notes.append("Arquivos de resultado de 2022 ainda não foram importados nesta base.")
    denom = {"pct": "qt_total_votos_validos do recorte",
             "delta_pp": "pct_2026 − pct_2022",
             "delta_rel_pct": "(votos_2026 − votos_2022) / votos_2022, se votos_2022 > 0",
             "metrica": args["metrica"]}
    return envelope(
        {"metrica": args["metrica"], "nr_partido": selected, "level": "municipio" if args["uf"] and not args["municipio"] else ("municipio" if args["municipio"] else "uf"),
         "years": {"2022": {k: y22[k] for k in ("available", "reason", "ano", "cd_eleicao", "choices_per_voter", "total_validos", "source")},
                   "2026": {k: y26[k] for k in ("available", "reason", "ano", "cd_eleicao", "choices_per_voter", "total_validos", "source")}},
         "parties": parties, "places": places},
        _meta(c26, {"denominators": denom}, notes))


def _contest_for_option(option_id: int, turno: int) -> dict:
    row = fetch_one(
        """SELECT o.id AS option_id, o.kind, o.nr_votavel, o.label, o.candidacy_id, o.cd_eleicao, o.cd_cargo, o.sg_ue,
                  cd.nm_candidato, cd.sq_candidato, cd.sg_partido, cd.nr_partido, cr.ds_sit_tot_turno,
                  e.ano_eleicao, e.ds_eleicao, c.id AS contest_id, c.nr_turno
           FROM core.vote_option o
           JOIN core.election e ON e.cd_eleicao = o.cd_eleicao
           JOIN core.contest c ON c.cd_eleicao = o.cd_eleicao AND c.cd_cargo = o.cd_cargo
                AND c.sg_ue = o.sg_ue AND c.nr_turno = :turno
           LEFT JOIN core.candidacy cd ON cd.id = o.candidacy_id
           LEFT JOIN core.candidacy_round cr ON cr.candidacy_id = o.candidacy_id AND cr.nr_turno = :turno
           WHERE o.id = :o AND o.kind = 'candidatura'""",
        o=option_id, turno=turno)
    if row is None:
        raise ApiError(404, "Candidatura não encontrada neste turno.", details={"option_id": option_id, "turno": turno})
    return row


@blp.route("/cross-compare")
@blp.arguments(CrossCompareArgs, location="query")
def cross_compare(args):
    """Compara duas candidaturas escolhidas independentemente (mesmo cargo), inclusive entre 2022 e 2026.

    `sq_candidato` não é chave global: cada lado é um `option_id` daquele ano. % = votos válidos da
    candidatura / `qt_total_votos_validos` do mesmo território e ano. Ausência ≠ zero.
    """
    ids = [int(x) for x in args["option_ids"].split(",")]
    if ids[0] == ids[1]:
        raise ApiError(400, "Escolha duas candidaturas distintas.")
    left, right = _contest_for_option(ids[0], args["turno"]), _contest_for_option(ids[1], args["turno"])
    if left["cd_cargo"] != right["cd_cargo"] or left["cd_cargo"] != args["cargo"]:
        raise ApiError(400, "As duas candidaturas precisam ser do mesmo cargo selecionado.")
    if left["sg_ue"] != right["sg_ue"]:
        raise ApiError(400, "As candidaturas precisam ser da mesma unidade (BR ou a mesma UF).")
    c_left = resolve_contest(left["cd_cargo"], args["turno"], args["uf"], args.get("municipio"), int(left["ano_eleicao"]))
    c_right = resolve_contest(right["cd_cargo"], args["turno"], args["uf"], args.get("municipio"), int(right["ano_eleicao"]))
    colors_l, colors_r = contest_colors(c_left["id"]), contest_colors(c_right["id"])
    options = []
    for side, c, opt in (("a", c_left, left), ("b", c_right, right)):
        t = _turnout(c)
        validos = int(t["qt_total_votos_validos"]) if t and t["qt_total_votos_validos"] is not None else None
        row = next((r for r in _ranking_rows(c, "candidatura") if r["option_id"] == opt["option_id"]), None)
        votos = int(row["qt_votos_validos"]) if row else 0
        options.append({
            "side": side, "option_id": opt["option_id"], "ano": int(opt["ano_eleicao"]),
            "cd_eleicao": opt["cd_eleicao"], "sg_ue": opt["sg_ue"], "sq_candidato": opt.get("sq_candidato"),
            "nr_votavel": opt["nr_votavel"], "label": opt["label"],
            "nm_candidato": opt["nm_candidato"], "sg_partido": opt["sg_partido"],
            "ds_sit_tot_turno": opt["ds_sit_tot_turno"],
            "qt_votos_validos": votos, "pct_validos": _pct(votos, validos),
            "qt_total_votos_validos": validos,
            "color": (colors_l if side == "a" else colors_r).get(opt["option_id"]),
        })
    uf_filter = args.get("uf")
    if uf_filter:
        raw = fetch_all("""
            SELECT m.cd_municipio_tse AS place_id, m.sg_uf, m.cd_municipio_tse, m.cd_municipio_ibge, m.nm_municipio AS nome,
                   ra.qt_votos_validos AS va, ta.qt_total_votos_validos AS ta,
                   rb.qt_votos_validos AS vb, tb.qt_total_votos_validos AS tb
            FROM core.municipality m
            LEFT JOIN agg.turnout_municipality ta ON ta.contest_id = :ca AND ta.cd_municipio_tse = m.cd_municipio_tse
            LEFT JOIN agg.result_municipality ra ON ra.contest_id = :ca AND ra.cd_municipio_tse = m.cd_municipio_tse
                 AND ra.option_id = :oa
            LEFT JOIN agg.turnout_municipality tb ON tb.contest_id = :cb AND tb.cd_municipio_tse = m.cd_municipio_tse
            LEFT JOIN agg.result_municipality rb ON rb.contest_id = :cb AND rb.cd_municipio_tse = m.cd_municipio_tse
                 AND rb.option_id = :ob
            WHERE m.sg_uf = :uf AND m.is_exterior IS NOT TRUE
            ORDER BY m.nm_municipio""",
                        ca=c_left["id"], cb=c_right["id"], oa=left["option_id"], ob=right["option_id"], uf=uf_filter)
        level = "municipio"
    else:
        raw = fetch_all("""
            SELECT s.sg_uf AS place_id, s.sg_uf, NULL::text AS cd_municipio_tse, NULL::text AS cd_municipio_ibge,
                   s.nm_uf AS nome,
                   ra.qt_votos_validos AS va, ta.qt_total_votos_validos AS ta,
                   rb.qt_votos_validos AS vb, tb.qt_total_votos_validos AS tb
            FROM core.state s
            LEFT JOIN agg.turnout_state ta ON ta.contest_id = :ca AND ta.sg_uf = s.sg_uf
            LEFT JOIN agg.result_state ra ON ra.contest_id = :ca AND ra.sg_uf = s.sg_uf AND ra.option_id = :oa
            LEFT JOIN agg.turnout_state tb ON tb.contest_id = :cb AND tb.sg_uf = s.sg_uf
            LEFT JOIN agg.result_state rb ON rb.contest_id = :cb AND rb.sg_uf = s.sg_uf AND rb.option_id = :ob
            WHERE s.sg_uf <> 'ZZ'
            ORDER BY s.sg_uf""",
                        ca=c_left["id"], cb=c_right["id"], oa=left["option_id"], ob=right["option_id"])
        level = "uf"
    places = []
    for r in raw:
        ta = int(r["ta"]) if r["ta"] is not None else None
        tb = int(r["tb"]) if r["tb"] is not None else None
        va = int(r["va"] or 0) if ta is not None else None
        vb = int(r["vb"] or 0) if tb is not None else None
        pa, pb = _pct(va, ta), _pct(vb, tb)
        places.append({
            "place_id": str(r["place_id"]), "sg_uf": r["sg_uf"], "nome": r["nome"],
            "cd_municipio_tse": r["cd_municipio_tse"], "cd_municipio_ibge": r["cd_municipio_ibge"],
            "a": {"qt_votos_validos": va, "pct_validos": pa, "qt_total_votos_validos": ta},
            "b": {"qt_votos_validos": vb, "pct_validos": pb, "qt_total_votos_validos": tb},
            "delta_pp": round(pb - pa, 4) if pa is not None and pb is not None else None,
            "status": "comparavel" if pa is not None and pb is not None else (
                "so_b" if pb is not None else ("so_a" if pa is not None else "ausente")),
        })
    notes = [
        "Cada lado usa o total de válidos do próprio ano e território. Não se somam votos de anos diferentes.",
        "sq_candidato não identifica a mesma pessoa entre 2022 e 2026: a comparação é a escolha explícita de cada lado.",
        "Ausência de um dos anos não é zero.",
        "Não interpreta diferença de votos como transferência individual de eleitores.",
    ]
    right_src = source_meta(c_right["sg_ue"], MUNZONA_KINDS, _ano(c_right))
    right_src.pop("_found", None)
    right_src.pop("_expected", None)
    return envelope(
        {"level": level, "options": options, "places": places},
        _meta(c_left, {
            "denominators": {
                "pct_validos": "votos válidos da candidatura / qt_total_votos_validos do mesmo recorte e ano",
                "delta_pp": "pct do lado B − pct do lado A",
            },
            "right_scope": contest_scope(c_right),
            "right_source": right_src,
        }, notes))
