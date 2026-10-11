"""Resolução de disputa (contest), metadados de fonte/cobertura e envelope de resposta."""
from flask import jsonify

from .db import fetch_all, fetch_one
from .errors import ApiError

ELECTION_BY_CARGO = {"1": "6257"}
DEFAULT_STATE_ELECTION = "6259"
PALETTE = ["#1d4ed8", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#65a30d",
           "#ea580c", "#0d9488", "#9333ea", "#4f46e5"]
OTHER_COLOR = "#94a3b8"
TIE_COLOR = "#374151"
NO_DATA_COLOR = "#e5e7eb"


def resolve_contest(cargo: str, turno: int, uf: str | None, municipio: str | None) -> dict:
    if municipio:
        mun = fetch_one("SELECT sg_uf FROM core.municipality WHERE cd_municipio_tse = :m", m=municipio)
        if mun is None:
            raise ApiError(404, f"Município {municipio} não encontrado.")
        if uf and uf != mun["sg_uf"]:
            raise ApiError(400, "Município não pertence à UF informada.")
        uf = mun["sg_uf"]
    if cargo == "1":
        sg_ue = "BR"
    else:
        if not uf:
            raise ApiError(400, "Para este cargo informe a UF: não existe disputa nacional.", details={"uf": "obrigatório"})
        if uf == "ZZ":
            raise ApiError(400, "Eleitores no exterior votam apenas para Presidente.")
        if cargo == "8" and uf != "DF":
            raise ApiError(400, "Deputado Distrital existe apenas no DF.")
        if cargo == "7" and uf == "DF":
            raise ApiError(400, "No DF o cargo equivalente é Deputado Distrital (cargo 8).")
        sg_ue = uf
    c = fetch_one(
        """SELECT c.id, c.cd_eleicao, c.nr_turno, c.cd_cargo, c.sg_ue, o.ds_cargo, o.system, e.ds_eleicao, e.dt_eleicao
           FROM core.contest c JOIN core.office o USING (cd_cargo) JOIN core.election e USING (cd_eleicao)
           WHERE c.cd_cargo = :cargo AND c.nr_turno = :turno AND c.sg_ue = :ue""",
        cargo=cargo, turno=turno, ue=sg_ue)
    if c is None:
        raise ApiError(404, "Disputa não disponível na base (turno não publicado pelo TSE ou recorte não importado).",
                       details={"cargo": cargo, "turno": turno, "sg_ue": sg_ue})
    seats = fetch_one("SELECT qt_vaga FROM core.seat WHERE cd_eleicao = :e AND sg_ue = :ue AND cd_cargo = :c",
                      e=c["cd_eleicao"], ue=sg_ue, c=cargo)
    c["qt_vaga"] = seats["qt_vaga"] if seats else None
    c["choices_per_voter"] = 2 if cargo == "5" and c["qt_vaga"] == 2 else 1
    c["uf"], c["municipio"] = uf, municipio
    return c


def source_meta(sg_ue: str, kinds: tuple[str, ...]) -> dict:
    scopes = [f"{k}:{sg_ue}" for k in kinds]
    rows = fetch_all(
        """SELECT p.scope_key, r.resource_key, r.member_name, r.source_generated_at, p.published_at
           FROM meta.publication p JOIN meta.import_run r ON r.id = p.import_run_id
           WHERE p.scope_key = ANY(:s)""", s=scopes)
    gen = [r["source_generated_at"] for r in rows if r["source_generated_at"]]
    pub = [r["published_at"] for r in rows]
    return {
        "source_generated_at": max(gen).isoformat() if gen else None,
        "imported_at": max(pub).isoformat() if pub else None,
        "resources": sorted({r["member_name"] for r in rows}),
        "_found": {r["scope_key"] for r in rows}, "_expected": scopes,
    }


def coverage_meta(src: dict, notes: list[str] | None = None) -> dict:
    found, expected = src.pop("_found"), src.pop("_expected")
    status = "completo" if len(found) == len(expected) else ("parcial" if found else "indisponivel")
    missing = [s for s in expected if s not in found]
    n = list(notes or [])
    if missing:
        n.append("Recortes ainda não importados: " + ", ".join(missing))
    return {"status": status, "published_scopes": len(found), "expected_scopes": len(expected), "notes": n}


def contest_scope(c: dict) -> dict:
    return {"cd_eleicao": c["cd_eleicao"], "ds_eleicao": c["ds_eleicao"], "nr_turno": c["nr_turno"],
            "cd_cargo": c["cd_cargo"], "ds_cargo": c["ds_cargo"], "sg_ue": c["sg_ue"], "sg_uf": c["uf"],
            "cd_municipio": c["municipio"], "system": c["system"], "qt_vaga": c["qt_vaga"],
            "choices_per_voter": c["choices_per_voter"]}


def envelope(data, meta: dict | None = None, status: int = 200):
    return jsonify({"data": data, "meta": meta or {}}), status


def contest_colors(contest_id: int) -> dict[int, str]:
    """Cor estável por candidatura dentro da disputa: ordem pelo total oficial de válidos da disputa inteira."""
    rows = fetch_all(
        """SELECT r.option_id FROM agg.result_state r JOIN core.vote_option o ON o.id = r.option_id
           WHERE r.contest_id = :c AND o.kind = 'candidatura'
           GROUP BY r.option_id, o.nr_votavel ORDER BY sum(r.qt_votos_validos) DESC, o.nr_votavel""", c=contest_id)
    return {r["option_id"]: (PALETTE[i] if i < len(PALETTE) else OTHER_COLOR) for i, r in enumerate(rows)}


def paging(page: int, page_size: int, total: int) -> dict:
    return {"page": page, "page_size": page_size, "total": total}
