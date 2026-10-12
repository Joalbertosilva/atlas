"""Leitura de cobertura pública de uma pesquisa registrada.

O CSV do TSE não traz intenção de voto. O detalhe do PesqEle exige sessão.
Aqui só extraímos percentuais que já aparecem em trechos de notícia, casados
com candidaturas oficiais do mesmo recorte — nunca inventamos número.
"""
from __future__ import annotations

import re
import unicodedata

CARGO_LABELS = (
    ("deputado distrital", "8"),
    ("deputado estadual", "7"),
    ("deputado federal", "6"),
    ("presidente", "1"),
    ("governador", "3"),
    ("senador", "5"),
)
_PCT = re.compile(r"(?<!\d)(\d{1,2}(?:[.,]\d{1,2})?)\s*%")
_SECOND_ROUND = re.compile(r"(2\D{0,2}\s*TURNO|SEGUNDO\s+TURNO)")


def fold(value: str) -> str:
    raw = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).upper()


def cargos_from_ds(ds_cargo: str | None) -> list[str]:
    text = fold(ds_cargo or "")
    found: list[str] = []
    for label, code in CARGO_LABELS:
        if fold(label) in text and code not in found:
            found.append(code)
    return found


def pick_cargo(ds_cargo: str | None, preferred: str | None = None) -> str | None:
    codes = cargos_from_ds(ds_cargo)
    if preferred and preferred in codes:
        return preferred
    return codes[0] if codes else preferred


def _aliases(label: str, nr: str | None) -> list[str]:
    folded = fold(label)
    parts = [p for p in folded.split() if p]
    aliases = [folded]
    if len(parts) >= 2:
        aliases.append(" ".join(parts[-2:]))
    if parts and len(parts[0]) >= 4:
        aliases.append(parts[0])
    if len(parts) >= 2 and len(parts[-1]) >= 5:
        aliases.append(parts[-1])
    if nr and re.fullmatch(r"[0-9]{2,5}", nr):
        aliases.append(f"N {nr}")
        aliases.append(f"NUMERO {nr}")
    # mais longo primeiro, para não casar "LULA" dentro de outro nome
    return sorted(set(aliases), key=len, reverse=True)


def extract_mentions(text: str, candidates: list[dict]) -> list[dict]:
    """Percentuais citados ao lado de um nome/número de candidatura oficial."""
    blob = fold(text)
    if not blob or not candidates:
        return []
    claimed: dict[int, dict] = {}
    used_spans: list[tuple[int, int]] = []

    def overlaps(a: int, b: int) -> bool:
        return any(not (b <= x or a >= y) for x, y in used_spans)

    for cand in candidates:
        oid = cand.get("option_id")
        if oid is None or oid in claimed:
            continue
        for alias in _aliases(str(cand.get("label") or ""), str(cand.get("nr_votavel") or "")):
            if len(alias) < 3:
                continue
            for mname in re.finditer(r"(?<![A-Z0-9])" + re.escape(alias) + r"(?![A-Z0-9])", blob):
                start, end = mname.start(), mname.end()
                window = blob[max(0, start - 28): min(len(blob), end + 28)]
                rel = max(0, start - 28)
                best = None
                for mp in _PCT.finditer(window):
                    pct = float(mp.group(1).replace(",", "."))
                    if pct <= 0 or pct >= 100:
                        continue
                    abs_a, abs_b = rel + mp.start(), rel + mp.end()
                    dist = min(abs(abs_a - end), abs(start - abs_b))
                    if dist > 28:
                        continue
                    if overlaps(abs_a, abs_b):
                        continue
                    if best is None or dist < best[0]:
                        best = (dist, pct, abs_a, abs_b)
                if best:
                    claimed[oid] = {
                        "option_id": oid,
                        "label": cand.get("label"),
                        "nr_votavel": cand.get("nr_votavel"),
                        "sg_partido": cand.get("sg_partido"),
                        "color": cand.get("color"),
                        "pct_mencao": round(best[1], 2),
                    }
                    used_spans.append((best[2], best[3]))
                    break
            if oid in claimed:
                break
    return list(claimed.values())


def is_second_round_coverage(text: str) -> bool:
    return bool(_SECOND_ROUND.search(fold(text)))


def runoff_candidates(candidates: list[dict]) -> list[dict]:
    out = []
    for row in candidates:
        sit = str(row.get("ds_sit_tot_turno") or "")
        if re.search(r"2", sit) and re.search(r"turno", sit, re.I):
            out.append(row)
    return out


def coverage_query(poll: dict, candidates: list[dict] | None = None) -> str:
    instituto = poll.get("nm_empresa_fantasia") or poll.get("nm_empresa") or "pesquisa eleitoral"
    cargo = poll.get("ds_cargo") or ""
    uf = poll.get("sg_uf") or ""
    proto = poll.get("nr_protocolo_registro") or ""
    janela = poll.get("janela")
    round_hint = "2 turno" if janela == "2" else "1 turno"
    names = [str(c.get("label") or "") for c in (candidates or [])[:2] if c.get("label")]
    parts = ["pesquisa eleitoral", instituto, cargo, uf, "2026", round_hint, proto, *names]
    return " ".join(p for p in parts if p)[:300]
