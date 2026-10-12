"""Busca online (via SearXNG próprio) e busca local de pesquisas registradas."""
import re

from flask import current_app, request
from flask_smorest import Blueprint

from ..db import fetch_all, fetch_one, scalar
from ..errors import ApiError
from ..schemas import PollLeituraArgs, PollSearchArgs, PollStatsArgs, SearchArgs
from ..scope import contest_colors, envelope, find_contest, paging
from ..search.poll_reading import (
    coverage_query,
    extract_mentions,
    is_second_round_coverage,
    pick_cargo,
    runoff_candidates,
)

PROTO_RE = re.compile(r"^[A-Z]{2}[0-9]{7,12}$")
PESQELE = "https://www.tse.jus.br/eleicoes/pesquisa-eleitorais/consulta-as-pesquisas-registradas"

blp = Blueprint("search", __name__, url_prefix="/api/search", description="Busca online e pesquisas registradas")


def _client_ip() -> str:
    return request.remote_addr or "?"


def _check_rate() -> None:
    ok, retry = current_app.extensions["atlas_search"].limiter.allow(_client_ip())
    if not ok:
        raise ApiError(429, "Limite de buscas por minuto atingido. Tente novamente em instantes.",
                       code="rate_limited", details={"retry_after_seconds": retry})


def _online(mode: str, args: dict):
    _check_rate()
    svc = current_app.extensions["atlas_search"]
    mun_name = None
    if args.get("municipio"):
        m = fetch_one("SELECT nm_municipio FROM core.municipality WHERE cd_municipio_tse = :m", m=args["municipio"])
        mun_name = m["nm_municipio"].title() if m else None
    query = svc.build_query(args["q"], args.get("uf"), mun_name, args.get("candidato"), mode)
    data, meta = svc.search(mode, query, args["page"])
    meta["notes"] = ["Resultados de terceiros, exibidos sem leitura das páginas. Datas apenas quando informadas "
                     "pelo mecanismo; verifique a data e a fonte antes de usar."]
    return envelope(data, meta)


def _route(mode: str):
    def view_get(args):
        return _online(mode, args)

    def view_post(args):
        return _online(mode, args)
    return view_get, view_post


for _mode, _path in (("web", "/web"), ("news", "/news"), ("fact-checks", "/fact-checks")):
    _g, _p = _route(_mode)
    _g.__name__, _p.__name__ = f"{_mode}_get".replace("-", "_"), f"{_mode}_post".replace("-", "_")
    blp.route(_path, methods=["GET"])(blp.arguments(SearchArgs, location="query")(_g))
    blp.route(_path, methods=["POST"], endpoint=_p.__name__)(blp.arguments(SearchArgs, location="json")(_p))


def _round_dates():
    row = fetch_one("""
        SELECT min(dt_eleicao)::date AS primeiro, max(dt_eleicao)::date AS segundo
        FROM core.election
        WHERE ano_eleicao = 2026 AND dt_eleicao >= date '2026-10-01' AND dt_eleicao < date '2026-11-01'""")
    return (row["primeiro"] if row else None), (row["segundo"] if row else None)


def _poll_source():
    return fetch_one("""SELECT r.source_generated_at, p.published_at FROM meta.publication p
                        JOIN meta.import_run r ON r.id = p.import_run_id WHERE p.scope_key = 'polls:BRASIL'""")


def _poll_notes():
    return [
        "Registro de pesquisa não é resultado: o cadastro do TSE não traz percentuais de intenção de voto.",
        "Primeiro e segundo turno não formam uma série só. Consulte o protocolo no PesqEle para o registro completo.",
    ]


def _poll_filters(args):
    primeiro, segundo = _round_dates()
    janela = args.get("janela") or "todas"
    params = dict(
        q=(args.get("q") or "").strip() or None,
        uf=args.get("uf"),
        cargo=args.get("cargo"),
        emp=args.get("empresa"),
        de=args.get("de"),
        ate=args.get("ate"),
        primeiro=primeiro,
        segundo=segundo,
        janela=janela,
    )
    where = """(CAST(:q AS text) IS NULL OR search_document @@ plainto_tsquery('portuguese', core.normalize_text(:q)))
               AND (CAST(:uf AS text) IS NULL OR sg_uf = :uf)
               AND (CAST(:cargo AS text) IS NULL OR core.normalize_text(ds_cargo) ILIKE '%' || core.normalize_text(:cargo) || '%')
               AND (CAST(:emp AS text) IS NULL OR core.normalize_text(nm_empresa || ' ' || coalesce(nm_empresa_fantasia, ''))
                    ILIKE '%' || core.normalize_text(:emp) || '%')
               AND (CAST(:de AS date) IS NULL OR dt_divulgacao >= :de)
               AND (CAST(:ate AS date) IS NULL OR dt_divulgacao <= :ate)
               AND (
                    CAST(:janela AS text) = 'todas'
                    OR (CAST(:janela AS text) = '1' AND CAST(:primeiro AS date) IS NOT NULL
                        AND coalesce(dt_fim_pesquisa, dt_divulgacao) <= :primeiro)
                    OR (CAST(:janela AS text) = '2' AND CAST(:primeiro AS date) IS NOT NULL
                        AND coalesce(dt_inicio_pesquisa, dt_divulgacao) > :primeiro)
               )"""
    return where, params, primeiro, segundo


def _pack_poll(row, *, detalhe=False):
    out = {k: row[k] for k in (
        "nr_protocolo_registro", "sg_uf", "nm_ue", "nm_empresa", "nm_empresa_fantasia", "ds_cargo",
        "dt_registro", "dt_inicio_pesquisa", "dt_fim_pesquisa", "dt_divulgacao", "qt_entrevistado", "vr_pesquisa")}
    if detalhe:
        for k in ("cd_eleicao", "nm_eleicao", "st_pesquisa_propria", "ds_metodologia_pesquisa",
                  "ds_plano_amostral", "ds_dado_municipio"):
            out[k] = row.get(k)
    for k in ("dt_registro", "dt_inicio_pesquisa", "dt_fim_pesquisa", "dt_divulgacao"):
        if out.get(k) is not None:
            out[k] = out[k].isoformat()
    out["vr_pesquisa"] = float(out["vr_pesquisa"]) if out.get("vr_pesquisa") is not None else None
    out["pesqele_url"] = PESQELE
    out["status"] = "registro_oficial_encontrado"
    return out


def _poll_janela(poll, primeiro):
    if not primeiro:
        return "todas"
    fim = poll.get("dt_fim_pesquisa") or poll.get("dt_divulgacao")
    inicio = poll.get("dt_inicio_pesquisa") or poll.get("dt_divulgacao")
    if inicio and str(inicio)[:10] > str(primeiro):
        return "2"
    if fim and str(fim)[:10] <= str(primeiro):
        return "1"
    return "todas"


def _official_candidates(cargo: str, uf: str | None, turno: int = 1, ano: int = 2026) -> tuple[list[dict], str | None]:
    from ..routes.results import _pct, _ranking_rows, _turnout
    try:
        c = find_contest(cargo, turno, None if cargo == "1" else uf, None, ano)
    except ApiError:
        return [], "recorte inválido"
    if c is None:
        return [], "Disputa ainda não publicada pelo TSE neste turno."
    t = _turnout(c)
    validos = t["qt_total_votos_validos"] if t else None
    colors = contest_colors(c["id"])
    rows = []
    for r in _ranking_rows(c, "candidatura"):
        if r["kind"] != "candidatura":
            continue
        rows.append({
            "option_id": r["option_id"], "label": r["label"], "nr_votavel": r["nr_votavel"],
            "sg_partido": r["sg_partido"], "sq_candidato": r.get("sq_candidato"),
            "cd_eleicao": r.get("cd_eleicao"), "sg_ue": r.get("sg_ue"),
            "qt_votos_validos": int(r["qt_votos_validos"]),
            "pct_validos": _pct(r["qt_votos_validos"], validos),
            "ds_sit_tot_turno": r.get("ds_sit_tot_turno"),
            "color": colors.get(r["option_id"]),
        })
    return rows, None


def _polls(args):
    where, params, primeiro, segundo = _poll_filters(args)
    params = {**params, "lim": args["page_size"], "off": (args["page"] - 1) * args["page_size"]}
    total = scalar(f"SELECT count(*) FROM polls.registered_poll WHERE {where}", **params)
    rows = fetch_all(f"""
        SELECT nr_protocolo_registro, sg_uf, nm_ue, nm_empresa, nm_empresa_fantasia, ds_cargo, dt_registro,
               dt_inicio_pesquisa, dt_fim_pesquisa, dt_divulgacao, qt_entrevistado, vr_pesquisa
        FROM polls.registered_poll WHERE {where}
        ORDER BY dt_divulgacao DESC NULLS LAST, nr_protocolo_registro LIMIT :lim OFFSET :off""", **params)
    packed = [_pack_poll(r) for r in rows]
    src = _poll_source()
    return envelope(packed, {
        "pagination": paging(args["page"], args["page_size"], total),
        "source": {"resource": "pesquisa_eleitoral_2026 (TSE, cadastro de registro)",
                   "source_generated_at": src["source_generated_at"].isoformat() if src and src["source_generated_at"] else None,
                   "imported_at": src["published_at"].isoformat() if src else None},
        "coverage": {"status": "completo" if src else "indisponivel"},
        "janela": {"turno": args.get("janela") or "todas",
                   "dt_primeiro_turno": primeiro.isoformat() if primeiro else None,
                   "dt_segundo_turno": segundo.isoformat() if segundo else None},
        "notes": _poll_notes()})


def _polls_stats(args):
    where, params, primeiro, segundo = _poll_filters({**args, "q": "", "de": None, "ate": None})
    total = scalar(f"SELECT count(*) FROM polls.registered_poll WHERE {where}", **params) or 0
    amostra = scalar(f"SELECT coalesce(sum(qt_entrevistado), 0) FROM polls.registered_poll WHERE {where}", **params) or 0
    institutos = scalar(
        f"SELECT count(DISTINCT coalesce(nm_empresa_fantasia, nm_empresa)) FROM polls.registered_poll WHERE {where}",
        **params) or 0
    por_mes = fetch_all(f"""
        SELECT to_char(coalesce(dt_divulgacao, dt_fim_pesquisa, dt_registro), 'YYYY-MM') AS mes,
               count(*) AS n, coalesce(sum(qt_entrevistado), 0) AS amostra
        FROM polls.registered_poll WHERE {where}
          AND coalesce(dt_divulgacao, dt_fim_pesquisa, dt_registro) IS NOT NULL
        GROUP BY 1 ORDER BY 1""", **params)
    por_cargo = fetch_all(f"""
        SELECT coalesce(ds_cargo, 'sem cargo') AS ds_cargo, count(*) AS n
        FROM polls.registered_poll WHERE {where}
        GROUP BY 1 ORDER BY n DESC, ds_cargo""", **params)
    institutos_top = fetch_all(f"""
        SELECT coalesce(nm_empresa_fantasia, nm_empresa, 'sem nome') AS instituto,
               count(*) AS n, coalesce(sum(qt_entrevistado), 0) AS amostra
        FROM polls.registered_poll WHERE {where}
        GROUP BY 1 ORDER BY n DESC, instituto LIMIT 12""", **params)
    src = _poll_source()
    for row in por_mes:
        row["n"] = int(row["n"])
        row["amostra"] = int(row["amostra"])
    for row in por_cargo:
        row["n"] = int(row["n"])
    for row in institutos_top:
        row["n"] = int(row["n"])
        row["amostra"] = int(row["amostra"])
    return envelope({
        "total": int(total),
        "institutos": int(institutos),
        "amostra": int(amostra),
        "dt_primeiro_turno": primeiro.isoformat() if primeiro else None,
        "dt_segundo_turno": segundo.isoformat() if segundo else None,
        "janela": args.get("janela") or "todas",
        "por_mes": por_mes,
        "por_cargo": por_cargo,
        "institutos_top": institutos_top,
    }, {
        "source": {"resource": "pesquisa_eleitoral_2026 (TSE, cadastro de registro)",
                   "source_generated_at": src["source_generated_at"].isoformat() if src and src["source_generated_at"] else None,
                   "imported_at": src["published_at"].isoformat() if src else None},
        "coverage": {"status": "completo" if src else "indisponivel"},
        "notes": _poll_notes(),
    })


def _load_poll(protocolo: str):
    if not PROTO_RE.fullmatch(protocolo or ""):
        raise ApiError(400, "Protocolo inválido.")
    row = fetch_one("""SELECT nr_protocolo_registro, cd_eleicao, nm_eleicao, sg_uf, nm_ue, nm_empresa,
                              nm_empresa_fantasia, ds_cargo, dt_registro, st_pesquisa_propria, dt_inicio_pesquisa,
                              dt_fim_pesquisa, dt_divulgacao, qt_entrevistado, vr_pesquisa, ds_metodologia_pesquisa,
                              ds_plano_amostral, ds_dado_municipio
                       FROM polls.registered_poll WHERE nr_protocolo_registro = :p""", p=protocolo)
    if row is None:
        raise ApiError(404, "Pesquisa não encontrada no cadastro importado.")
    return row


@blp.route("/polls/<string:protocolo>")
def poll_detail(protocolo):
    row = _load_poll(protocolo)
    primeiro, segundo = _round_dates()
    packed = _pack_poll(row, detalhe=True)
    packed["janela"] = _poll_janela(row, primeiro)
    src = _poll_source()
    return envelope(packed, {
        "source": {"resource": "pesquisa_eleitoral_2026 (TSE, cadastro de registro)",
                   "source_generated_at": src["source_generated_at"].isoformat() if src and src["source_generated_at"] else None,
                   "imported_at": src["published_at"].isoformat() if src else None},
        "janela": {"turno": packed["janela"],
                   "dt_primeiro_turno": primeiro.isoformat() if primeiro else None,
                   "dt_segundo_turno": segundo.isoformat() if segundo else None},
        "notes": _poll_notes(),
    })


@blp.route("/polls/<string:protocolo>/leitura", methods=["POST"], endpoint="poll_leitura_post")
@blp.arguments(PollLeituraArgs, location="json")
def poll_leitura(args, protocolo):
    _check_rate()
    row = _load_poll(protocolo)
    packed = _pack_poll(row, detalhe=True)
    primeiro, segundo = _round_dates()
    janela = _poll_janela(row, primeiro)
    packed["janela"] = janela
    cargo = pick_cargo(row["ds_cargo"], args.get("cargo"))
    uf = None if cargo == "1" or (row["sg_uf"] in (None, "BR")) else row["sg_uf"]
    urna, urna_note = _official_candidates(cargo, uf, 1) if cargo else ([], "Cargo da pesquisa não identificado.")
    query = coverage_query(packed, urna)
    svc = current_app.extensions["atlas_search"]
    hits, search_meta = svc.search("news", query, 1)

    def _merge_web() -> None:
        nonlocal hits, search_meta
        extra, extra_meta = svc.search("web", query, 1)
        urls = {h.get("url") for h in hits}
        for hit in extra:
            if hit.get("url") and hit.get("url") not in urls:
                hits.append(hit)
                urls.add(hit.get("url"))
        search_meta = {**search_meta, "web_fallback": extra_meta}

    notes_extra = None
    if janela == "2":
        extract_urna = runoff_candidates(urna)
        focused = [h for h in hits if is_second_round_coverage(f"{h.get('title') or ''} {h.get('snippet') or ''}")]
        if not focused:
            _merge_web()
            focused = [h for h in hits if is_second_round_coverage(f"{h.get('title') or ''} {h.get('snippet') or ''}")]
        extract_hits = focused
        if not focused:
            notes_extra = "A cobertura localizada ainda não cita o 2º turno desta coleta; sem percentual extraído para não misturar com o 1º."
    else:
        extract_urna = urna
        blob = " ".join(f"{h.get('title') or ''} {h.get('snippet') or ''}" for h in hits)
        if not extract_mentions(blob, urna):
            _merge_web()
        extract_hits = hits
    blob = " ".join(f"{h.get('title') or ''} {h.get('snippet') or ''}" for h in extract_hits)
    mencoes = extract_mentions(blob, extract_urna)
    by_id = {m["option_id"]: m for m in mencoes}
    for hit in extract_hits:
        found = extract_mentions(f"{hit.get('title') or ''} {hit.get('snippet') or ''}", extract_urna)
        for item in found:
            by_id.setdefault(item["option_id"], item)
            by_id[item["option_id"]].setdefault("fonte_url", hit.get("url"))
            by_id[item["option_id"]].setdefault("trecho", (hit.get("snippet") or hit.get("title") or "")[:280])
    mencoes = list(by_id.values())
    confronto = None
    if janela == "1" and mencoes and urna:
        urna_by = {r["option_id"]: r for r in urna}
        confronto = []
        for m in mencoes:
            off = urna_by.get(m["option_id"])
            if not off or off.get("pct_validos") is None:
                continue
            confronto.append({
                "option_id": m["option_id"], "label": m["label"], "nr_votavel": m["nr_votavel"],
                "color": m.get("color") or off.get("color"),
                "pct_mencao": m["pct_mencao"], "pct_urna": off["pct_validos"],
                "delta_pp": round(m["pct_mencao"] - off["pct_validos"], 2),
            })
    notes = [
        "O cadastro do TSE não contém intenção de voto. Os percentuais abaixo, se houver, foram citados na cobertura jornalística encontrada agora — não são o arquivo da pesquisa.",
        "Consulta enviada a mecanismos públicos pelo servidor do Atlas. Abra a matéria original para conferir.",
    ]
    if janela == "2":
        notes.append("Esta coleta é posterior ao 1º turno. A urna do 2º ainda não foi publicada; o confronto com resultado oficial fica para o 1º turno.")
    if notes_extra:
        notes.append(notes_extra)
    if urna_note:
        notes.append(urna_note)
    src = _poll_source()
    return envelope({
        "poll": packed,
        "janela": janela,
        "cargo_usado": cargo,
        "mencoes": mencoes,
        "urna": urna[:12],
        "confronto": confronto,
        "hits": hits,
    }, {
        "source": {"resource": "pesquisa_eleitoral_2026 + cobertura pública",
                   "source_generated_at": src["source_generated_at"].isoformat() if src and src["source_generated_at"] else None,
                   "imported_at": src["published_at"].isoformat() if src else None},
        "search": search_meta,
        "notes": notes,
    })


@blp.route("/polls/stats", methods=["GET"])
@blp.arguments(PollStatsArgs, location="query")
def polls_stats_get(args):
    return _polls_stats(args)


@blp.route("/polls/stats", methods=["POST"], endpoint="polls_stats_post")
@blp.arguments(PollStatsArgs, location="json")
def polls_stats_post(args):
    return _polls_stats(args)


@blp.route("/polls", methods=["GET"])
@blp.arguments(PollSearchArgs, location="query")
def polls_get(args):
    return _polls(args)


@blp.route("/polls", methods=["POST"], endpoint="polls_post")
@blp.arguments(PollSearchArgs, location="json")
def polls_post(args):
    return _polls(args)


@blp.route("/status")
def status():
    svc = current_app.extensions["atlas_search"]
    data = svc.status()
    try:
        data["cache_entries"] = scalar("SELECT count(*) FROM app.search_cache WHERE expires_at > now()")
    except Exception:  # noqa: BLE001
        data["cache_entries"] = None
    data["rate_limit_per_minute"] = svc.limiter.per_minute
    data["cache_ttl_seconds"] = svc.ttl
    data["page_reading"] = "desativado"
    return envelope(data)
