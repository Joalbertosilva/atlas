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

# Cores convencionais de leitura por partido (PT vermelho, PL amarelo).
# O TSE não publica paleta de candidatura — isto não é cor oficial da urna.
PARTY_COLORS = {
    "PT": "#E30613",
    "PL": "#F5C400",
    "PDT": "#FE0000",
    "PSOL": "#FFCC00",
    "PSDB": "#0080C8",
    "MDB": "#00A859",
    "UNIAO": "#00AEEF",
    "PP": "#1E4D8C",
    "REPUBLICANOS": "#0A2F8C",
    "PSD": "#FF8A00",
    "NOVO": "#F37021",
    "PSB": "#E31C23",
    "PCDOB": "#DA251C",
    "REDE": "#00A99D",
    "PV": "#006633",
    "PSTU": "#ED1C24",
    "PCB": "#CC0000",
    "UP": "#7A0019",
    "SOLIDARIEDADE": "#F68B1F",
    "CIDADANIA": "#EC008C",
    "AVANTE": "#ED3237",
    "PODE": "#2D8C3C",
    "PODEMOS": "#2D8C3C",
    "PRD": "#1B4F9C",
    "DC": "#0A5BA8",
    "AGIR": "#1E5AA8",
    "MOBILIZA": "#1B4B8C",
    "PRTB": "#0033A0",
    "PMB": "#00A0E0",
    "PCO": "#8B0000",
    "MISSAO": "#C2410C",
    "PR": "#F5C400",
}
NR_PARTIDO_COLORS = {
    "10": "#0A2F8C", "11": "#1E4D8C", "12": "#FE0000", "13": "#E30613", "14": "#C2410C",
    "15": "#00A859", "16": "#ED1C24", "18": "#00A99D", "20": "#2D8C3C", "21": "#CC0000",
    "22": "#F5C400", "23": "#EC008C", "27": "#0A5BA8", "28": "#0033A0", "29": "#8B0000",
    "30": "#F37021", "33": "#1B4B8C", "36": "#1E5AA8", "40": "#E31C23", "43": "#006633",
    "44": "#00AEEF", "45": "#0080C8", "50": "#FFCC00", "55": "#FF8A00", "65": "#DA251C",
    "70": "#ED3237", "77": "#F68B1F", "80": "#7A0019",
}


def _norm_party(sg: str | None) -> str:
    if not sg:
        return ""
    raw = sg.upper().replace(".", "").replace(" ", "").replace("Ã", "A").replace("Ç", "C")
    return raw.replace("UNIÃO", "UNIAO").replace("MISSÃO", "MISSAO")


def party_hex(sg_partido: str | None, nr_partido: str | None = None) -> str | None:
    """Cor convencional da sigla ou do número; None se não houver correspondência."""
    key = _norm_party(sg_partido)
    if key and key in PARTY_COLORS:
        return PARTY_COLORS[key]
    nr = (nr_partido or "").strip()
    if nr in NR_PARTIDO_COLORS:
        return NR_PARTIDO_COLORS[nr]
    return None


def color_for_party(sg_partido: str | None, nr_partido: str | None = None, fallback_index: int = 0) -> str:
    found = party_hex(sg_partido, nr_partido)
    if found:
        return found
    if 0 <= fallback_index < len(PALETTE):
        return PALETTE[fallback_index]
    return OTHER_COLOR


def _ue_for(cargo: str, uf: str | None, municipio: str | None) -> tuple[str, str | None]:
    if municipio:
        mun = fetch_one("SELECT sg_uf FROM core.municipality WHERE cd_municipio_tse = :m", m=municipio)
        if mun is None:
            raise ApiError(404, f"Município {municipio} não encontrado.")
        if uf and uf != mun["sg_uf"]:
            raise ApiError(400, "Município não pertence à UF informada.")
        uf = mun["sg_uf"]
    if cargo == "1":
        return "BR", uf
    if not uf:
        raise ApiError(400, "Para este cargo informe a UF: não existe disputa nacional.", details={"uf": "obrigatório"})
    if uf == "ZZ":
        raise ApiError(400, "Eleitores no exterior votam apenas para Presidente.")
    if cargo == "8" and uf != "DF":
        raise ApiError(400, "Deputado Distrital existe apenas no DF.")
    if cargo == "7" and uf == "DF":
        raise ApiError(400, "No DF o cargo equivalente é Deputado Distrital (cargo 8).")
    return uf, uf


def find_contest(cargo: str, turno: int, uf: str | None, municipio: str | None, ano: int = 2026) -> dict | None:
    sg_ue, uf = _ue_for(cargo, uf, municipio)
    c = fetch_one(
        """SELECT c.id, c.cd_eleicao, c.nr_turno, c.cd_cargo, c.sg_ue, o.ds_cargo, o.system,
                  e.ds_eleicao, e.dt_eleicao, e.ano_eleicao
           FROM core.contest c JOIN core.office o USING (cd_cargo) JOIN core.election e USING (cd_eleicao)
           WHERE c.cd_cargo = :cargo AND c.nr_turno = :turno AND c.sg_ue = :ue AND e.ano_eleicao = :ano""",
        cargo=cargo, turno=turno, ue=sg_ue, ano=ano)
    if c is None:
        return None
    seats = fetch_one("SELECT qt_vaga FROM core.seat WHERE cd_eleicao = :e AND sg_ue = :ue AND cd_cargo = :c",
                      e=c["cd_eleicao"], ue=sg_ue, c=cargo)
    c["qt_vaga"] = seats["qt_vaga"] if seats else None
    c["choices_per_voter"] = 2 if cargo == "5" and c["qt_vaga"] == 2 else 1
    c["uf"], c["municipio"] = uf, municipio
    return c


def resolve_contest(cargo: str, turno: int, uf: str | None, municipio: str | None, ano: int = 2026) -> dict:
    c = find_contest(cargo, turno, uf, municipio, ano)
    if c is None:
        sg_ue, _ = _ue_for(cargo, uf, municipio)
        raise ApiError(404, "Disputa não disponível na base (turno não publicado pelo TSE ou recorte não importado).",
                       details={"cargo": cargo, "turno": turno, "sg_ue": sg_ue, "ano": ano})
    return c


def source_meta(sg_ue: str, kinds: tuple[str, ...], ano: int = 2026) -> dict:
    scopes = [f"{k}:{sg_ue}" if int(ano or 2026) == 2026 else f"{k}:{int(ano)}:{sg_ue}" for k in kinds]
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
    return {"cd_eleicao": c["cd_eleicao"], "ds_eleicao": c["ds_eleicao"], "ano_eleicao": c.get("ano_eleicao"),
            "nr_turno": c["nr_turno"], "cd_cargo": c["cd_cargo"], "ds_cargo": c["ds_cargo"], "sg_ue": c["sg_ue"],
            "sg_uf": c["uf"], "cd_municipio": c["municipio"], "system": c["system"], "qt_vaga": c["qt_vaga"],
            "choices_per_voter": c["choices_per_voter"]}


def envelope(data, meta: dict | None = None, status: int = 200):
    return jsonify({"data": data, "meta": meta or {}}), status


def contest_colors(contest_id: int) -> dict[int, str]:
    """Cor por partido da candidatura (PT vermelho, PL amarelo). Sem sigla, cai na paleta de leitura."""
    rows = fetch_all(
        """SELECT r.option_id, o.nr_votavel, cd.sg_partido, cd.nr_partido
           FROM agg.result_state r
           JOIN core.vote_option o ON o.id = r.option_id
           LEFT JOIN core.candidacy cd ON cd.id = o.candidacy_id
           WHERE r.contest_id = :c AND o.kind = 'candidatura'
           GROUP BY r.option_id, o.nr_votavel, cd.sg_partido, cd.nr_partido
           ORDER BY sum(r.qt_votos_validos) DESC, o.nr_votavel""", c=contest_id)
    out: dict[int, str] = {}
    unknown = 0
    for r in rows:
        found = party_hex(r["sg_partido"], r["nr_partido"] or r["nr_votavel"])
        if found:
            out[r["option_id"]] = found
        else:
            out[r["option_id"]] = PALETTE[unknown] if unknown < len(PALETTE) else OTHER_COLOR
            unknown += 1
    return out


def paging(page: int, page_size: int, total: int) -> dict:
    return {"page": page, "page_size": page_size, "total": total}
