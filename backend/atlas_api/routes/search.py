"""Busca online (via SearXNG próprio) e busca local de pesquisas registradas."""
from flask import current_app, request
from flask_smorest import Blueprint

from ..db import fetch_all, fetch_one, scalar
from ..errors import ApiError
from ..schemas import PollSearchArgs, SearchArgs
from ..scope import envelope, paging

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


def _polls(args):
    params = dict(q=args["q"].strip() or None, uf=args["uf"], cargo=args["cargo"], emp=args["empresa"],
                  de=args["de"], ate=args["ate"], lim=args["page_size"], off=(args["page"] - 1) * args["page_size"])
    where = """(CAST(:q AS text) IS NULL OR search_document @@ plainto_tsquery('portuguese', core.normalize_text(:q)))
               AND (CAST(:uf AS text) IS NULL OR sg_uf = :uf)
               AND (CAST(:cargo AS text) IS NULL OR core.normalize_text(ds_cargo) ILIKE '%' || core.normalize_text(:cargo) || '%')
               AND (CAST(:emp AS text) IS NULL OR core.normalize_text(nm_empresa || ' ' || coalesce(nm_empresa_fantasia, ''))
                    ILIKE '%' || core.normalize_text(:emp) || '%')
               AND (CAST(:de AS date) IS NULL OR dt_divulgacao >= :de)
               AND (CAST(:ate AS date) IS NULL OR dt_divulgacao <= :ate)"""
    total = scalar(f"SELECT count(*) FROM polls.registered_poll WHERE {where}", **params)
    rows = fetch_all(f"""
        SELECT nr_protocolo_registro, sg_uf, nm_ue, nm_empresa, nm_empresa_fantasia, ds_cargo, dt_registro,
               dt_inicio_pesquisa, dt_fim_pesquisa, dt_divulgacao, qt_entrevistado, vr_pesquisa
        FROM polls.registered_poll WHERE {where}
        ORDER BY dt_divulgacao DESC NULLS LAST, nr_protocolo_registro LIMIT :lim OFFSET :off""", **params)
    for r in rows:
        for k in ("dt_registro", "dt_inicio_pesquisa", "dt_fim_pesquisa", "dt_divulgacao"):
            if r[k] is not None:
                r[k] = r[k].isoformat()
        r["vr_pesquisa"] = float(r["vr_pesquisa"]) if r["vr_pesquisa"] is not None else None
        # O detalhe por protocolo no PesqEle exige sessão no sistema (detalhar.xhtml).
        # Ligamos à consulta pública oficial; o protocolo é o identificador a buscar lá.
        r["pesqele_url"] = "https://www.tse.jus.br/eleicoes/pesquisa-eleitorais/consulta-as-pesquisas-registradas"
        r["status"] = "registro_oficial_encontrado"
    src = fetch_one("""SELECT r.source_generated_at, p.published_at FROM meta.publication p
                       JOIN meta.import_run r ON r.id = p.import_run_id WHERE p.scope_key = 'polls:BRASIL'""")
    return envelope(rows, {
        "pagination": paging(args["page"], args["page_size"], total),
        "source": {"resource": "pesquisa_eleitoral_2026 (TSE, cadastro de registro)",
                   "source_generated_at": src["source_generated_at"].isoformat() if src and src["source_generated_at"] else None,
                   "imported_at": src["published_at"].isoformat() if src else None},
        "coverage": {"status": "completo" if src else "indisponivel"},
        "notes": ["Registro de pesquisa não é resultado: o cadastro do TSE não traz percentuais de intenção de voto.",
                  "Consulte o protocolo no sistema PesqEle do TSE para ver o registro completo."]})


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
