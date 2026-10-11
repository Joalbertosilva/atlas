"""Navegação territorial: município → zona → local de votação → seção."""
from flask_smorest import Blueprint

from ..db import fetch_all, fetch_one, scalar
from ..errors import ApiError
from ..schemas import PlacesArgs, SectionsArgs, TurnoCargoArgs
from ..scope import contest_colors, contest_scope, coverage_meta, envelope, paging, resolve_contest, source_meta

blp = Blueprint("territory", __name__, url_prefix="/api", description="Zonas, locais e seções")


def _mun(cd: str) -> dict:
    if not (len(cd) == 5 and cd.isdigit()):
        raise ApiError(400, "Código de município TSE deve ter 5 dígitos.")
    m = fetch_one("SELECT * FROM core.municipality WHERE cd_municipio_tse = :m", m=cd)
    if m is None:
        raise ApiError(404, "Município não encontrado.")
    return m


@blp.route("/municipalities/<cd_municipio>/zones")
@blp.arguments(TurnoCargoArgs, location="query")
def zones(args, cd_municipio):
    m = _mun(cd_municipio)
    c = resolve_contest(args["cargo"], args["turno"], m["sg_uf"], cd_municipio)
    colors = contest_colors(c["id"])
    rows = fetch_all("""
        WITH t AS (
            SELECT nr_zona, sum(qt_aptos) qt_aptos, sum(qt_comparecimento) qt_comparecimento,
                   sum(qt_total_votos_validos) qt_total_votos_validos, sum(qt_votos_brancos) qt_votos_brancos,
                   sum(qt_total_votos_nulos) qt_total_votos_nulos, sum(qt_total_secoes) qt_total_secoes
            FROM fact.turnout_munzona WHERE contest_id = :c AND cd_municipio_tse = :m GROUP BY nr_zona),
        v AS (
            SELECT v.nr_zona, v.option_id, o.label, sum(v.qt_votos_validos) qv,
                   rank() OVER (PARTITION BY v.nr_zona ORDER BY sum(v.qt_votos_validos) DESC) rk
            FROM fact.vote_munzona v JOIN core.vote_option o ON o.id = v.option_id AND o.kind = 'candidatura'
            WHERE v.contest_id = :c AND v.cd_municipio_tse = :m GROUP BY 1, 2, 3),
        s AS (
            SELECT sc.nr_zona, count(*) FILTER (WHERE ts.section_id IS NOT NULL) AS sections_loaded,
                   count(*) AS sections_registered
            FROM core.section sc LEFT JOIN fact.turnout_section ts ON ts.section_id = sc.id AND ts.contest_id = :c
            WHERE sc.cd_municipio_tse = :m GROUP BY 1)
        SELECT t.*, coalesce(s.sections_loaded, 0) sections_loaded, coalesce(s.sections_registered, 0) sections_registered,
               (SELECT json_agg(json_build_object('option_id', option_id, 'label', label, 'qt_votos_validos', qv))
                FROM v WHERE v.nr_zona = t.nr_zona AND v.rk = 1 AND v.qv > 0) AS leaders
        FROM t LEFT JOIN s USING (nr_zona) ORDER BY t.nr_zona::int""", c=c["id"], m=cd_municipio)
    for r in rows:
        for k in list(r):
            if k.startswith("qt_") and r[k] is not None:
                r[k] = int(r[k])
        leaders = r.pop("leaders") or []
        r["tie"] = len(leaders) > 1
        r["leader"] = None if not leaders else {**leaders[0], "color": colors.get(leaders[0]["option_id"]),
                                                "pct_validos": round(100 * leaders[0]["qt_votos_validos"] /
                                                                     r["qt_total_votos_validos"], 4)
                                                if r["qt_total_votos_validos"] else None}
    src = source_meta(c["sg_ue"], ("munzona_cand", "munzona_detalhe"))
    return envelope(rows, {"scope": contest_scope(c), "source": src, "coverage": coverage_meta(src),
                           "municipality": {"cd_municipio_tse": m["cd_municipio_tse"], "nm_municipio": m["nm_municipio"],
                                            "sg_uf": m["sg_uf"], "cd_municipio_ibge": m["cd_municipio_ibge"]}})


@blp.route("/municipalities/<cd_municipio>/polling-places")
@blp.arguments(PlacesArgs, location="query")
def polling_places(args, cd_municipio):
    m = _mun(cd_municipio)
    params = dict(m=cd_municipio, z=args["zona"], q=args["q"], lim=args["page_size"],
                  off=(args["page"] - 1) * args["page_size"])
    where = """p.cd_municipio_tse = :m AND (CAST(:z AS text) IS NULL OR p.nr_zona = :z)
               AND (CAST(:q AS text) IS NULL OR core.normalize_text(p.nm_local_votacao || ' ' || coalesce(p.ds_endereco, '')
                    || ' ' || coalesce(p.nm_bairro, '')) LIKE '%' || core.normalize_text(:q) || '%')"""
    total = scalar(f"SELECT count(*) FROM core.polling_place p WHERE {where}", **params)
    rows = fetch_all(f"""
        SELECT p.id AS polling_place_id, p.nr_zona, p.nr_local_votacao, p.nm_local_votacao, p.ds_tipo_local,
               p.ds_endereco, p.nm_bairro, p.coord_status,
               CASE WHEN p.coord_status = 'valida' THEN p.latitude END AS latitude,
               CASE WHEN p.coord_status = 'valida' THEN p.longitude END AS longitude,
               count(s.id) AS qt_secoes, coalesce(sum(s.qt_eleitor_secao), 0) AS qt_eleitor
        FROM core.polling_place p LEFT JOIN core.section s ON s.polling_place_id = p.id
        WHERE {where}
        GROUP BY p.id ORDER BY p.nr_zona::int, p.nm_local_votacao LIMIT :lim OFFSET :off""", **params)
    for r in rows:
        r["qt_eleitor"] = int(r["qt_eleitor"])
    src = source_meta(m["sg_uf"], ("locais",))
    return envelope(rows, {"pagination": paging(args["page"], args["page_size"], total), "source": src,
                           "coverage": coverage_meta(src, ["Locais e vínculo com seções vêm do cadastro "
                                                           "eleitorado_local_votacao (mesma eleição, 1º turno)."]),
                           "municipality": {"cd_municipio_tse": m["cd_municipio_tse"], "nm_municipio": m["nm_municipio"],
                                            "sg_uf": m["sg_uf"]}})


@blp.route("/sections")
@blp.arguments(SectionsArgs, location="query")
def sections(args):
    m = _mun(args["municipio"])
    params = dict(m=args["municipio"], z=args["zona"], l=args["local"], lim=args["page_size"],
                  off=(args["page"] - 1) * args["page_size"])
    where = """s.cd_municipio_tse = :m AND (CAST(:z AS text) IS NULL OR s.nr_zona = :z)
               AND (CAST(:l AS integer) IS NULL OR s.polling_place_id = :l)"""
    total = scalar(f"SELECT count(*) FROM core.section s WHERE {where}", **params)
    rows = fetch_all(f"""
        SELECT s.id AS section_id, s.nr_zona, s.nr_secao, s.polling_place_id, p.nm_local_votacao, p.ds_tipo_local,
               s.link_status, s.ds_tipo_secao_agregada, s.nr_secao_principal, s.qt_eleitor_secao
        FROM core.section s LEFT JOIN core.polling_place p ON p.id = s.polling_place_id
        WHERE {where} ORDER BY s.nr_zona::int, s.nr_secao::int LIMIT :lim OFFSET :off""", **params)
    return envelope(rows, {"pagination": paging(args["page"], args["page_size"], total),
                           "municipality": {"cd_municipio_tse": m["cd_municipio_tse"], "nm_municipio": m["nm_municipio"],
                                            "sg_uf": m["sg_uf"]},
                           "link_status_legend": {
                               "confirmado": "local do cadastro coincide com o NR_LOCAL_VOTACAO do arquivo de votos",
                               "somente_cadastro": "seção no cadastro de locais, sem votos carregados para ela",
                               "somente_resultado": "seção com votos, mas sem local identificado no cadastro",
                               "divergente": "cadastro e arquivo de votos indicam locais diferentes",
                               "sem_vinculo": "local não identificado na base"}})


@blp.route("/sections/<int:section_id>/results")
@blp.arguments(TurnoCargoArgs, location="query")
def section_results(args, section_id):
    s = fetch_one("""
        SELECT s.id AS section_id, s.cd_municipio_tse, m.nm_municipio, m.sg_uf, s.nr_zona, s.nr_secao, s.link_status,
               s.polling_place_id, p.nm_local_votacao, p.ds_tipo_local, p.ds_endereco, p.nm_bairro, p.coord_status,
               CASE WHEN p.coord_status = 'valida' THEN p.latitude END AS latitude,
               CASE WHEN p.coord_status = 'valida' THEN p.longitude END AS longitude,
               s.ds_tipo_secao_agregada, s.nr_secao_principal, s.qt_eleitor_secao
        FROM core.section s JOIN core.municipality m USING (cd_municipio_tse)
        LEFT JOIN core.polling_place p ON p.id = s.polling_place_id WHERE s.id = :s""", s=section_id)
    if s is None:
        raise ApiError(404, "Seção não encontrada.")
    c = resolve_contest(args["cargo"], args["turno"], s["sg_uf"], s["cd_municipio_tse"]) if not (
        s["sg_uf"] == "ZZ" and args["cargo"] == "1") else resolve_contest("1", args["turno"], None, None)
    turnout = fetch_one("""SELECT qt_aptos, qt_comparecimento, qt_abstencoes, qt_votos_nominais, qt_votos_brancos,
                                  qt_votos_nulos, qt_votos_legenda, qt_votos_anulados_apu_sep, st_secao_instalada,
                                  st_secao_anulada, ds_origem_voto
                           FROM fact.turnout_section WHERE contest_id = :c AND section_id = :s""", c=c["id"], s=section_id)
    colors = contest_colors(c["id"])
    rows = fetch_all("""
        SELECT o.id AS option_id, o.kind, o.nr_votavel, o.label, cd.sg_partido, v.qt_votos
        FROM fact.vote_section v JOIN core.vote_option o ON o.id = v.option_id
        LEFT JOIN core.candidacy cd ON cd.id = o.candidacy_id
        WHERE v.sg_ue = :ue AND v.section_id = :s AND v.contest_id = :c
        ORDER BY (o.kind <> 'candidatura'), v.qt_votos DESC, o.nr_votavel""", ue=c["sg_ue"], s=section_id, c=c["id"])
    for r in rows:
        r["color"] = colors.get(r["option_id"])
    src = source_meta(c["sg_ue"], ("secao", "detalhe_secao"))
    notes = ["Na seção, qt_votos é o total digitado para a opção; o arquivo de seção não separa votos válidos de "
             "anulados sub judice — a totalização oficial por município/zona é a referência."]
    if s["link_status"] != "confirmado":
        notes.append("Local não identificado na base para esta seção (ou vínculo não confirmado).")
    if not rows:
        notes.append("Sem votos por seção carregados para este cargo/recorte.")
    return envelope({"section": s, "turnout": turnout, "results": rows},
                    {"scope": contest_scope(c), "source": src, "coverage": coverage_meta(src, notes), "notes": notes})
