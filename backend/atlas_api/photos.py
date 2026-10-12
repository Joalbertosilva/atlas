"""Fotos oficiais do TSE. 2022 só existe no ZIP do CDN (não no portal de resultados)."""
from __future__ import annotations

import io
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

UE_RE = re.compile(r"^(BR|[A-Z]{2})$")
SQ_RE = re.compile(r"^\d{5,14}$")
ZIP_MAX = 40 * 1024 * 1024
FILE_MAX = 2 * 1024 * 1024
CACHE = Path("/tmp/atlas_fotos")
ZIP_URL = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ano}/fotos/foto_cand{ano}_{ue}_div.zip"


class PhotoNotFound(Exception):
    pass


class PhotoUnavailable(Exception):
    pass


def photo_zip_url(ano: int, ue: str) -> str:
    if ano != 2022:
        raise PhotoNotFound("ZIP de fotos só está publicado pelo TSE para 2022 neste padrão.")
    if not UE_RE.match(ue):
        raise PhotoNotFound("UE inválida.")
    return ZIP_URL.format(ano=ano, ue=ue)


def cached_photo_path(ano: int, ue: str, sq: str) -> Path | None:
    folder = CACHE / str(ano) / ue
    if not folder.is_dir():
        return None
    for name in _candidate_names(ue, sq):
        path = folder / name
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _candidate_names(ue: str, sq: str) -> list[str]:
    stem = f"F{ue}{sq}_div"
    return [f"{stem}.jpg", f"{stem}.jpeg", f"{stem}.JPG", f"{stem}.JPEG"]


def fetch_official_photo(ano: int, ue: str, sq: str) -> tuple[Path, str]:
    ue = ue.strip().upper()
    sq = sq.strip()
    if ano not in (2022,) or not UE_RE.match(ue) or not SQ_RE.match(sq):
        raise PhotoNotFound("Parâmetros de foto inválidos.")
    cached = cached_photo_path(ano, ue, sq)
    if cached:
        return cached, "image/jpeg"
    url = photo_zip_url(ano, ue)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AtlasEleitoral/0.1 (fotos oficiais TSE dados abertos)", "Accept": "application/zip"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read(ZIP_MAX + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise PhotoNotFound("ZIP de fotos desta UE não está no CDN do TSE.") from exc
        raise PhotoUnavailable(f"CDN do TSE recusou o ZIP ({exc.code}).") from exc
    except OSError as exc:
        raise PhotoUnavailable("Não foi possível baixar o ZIP oficial de fotos.") from exc
    if len(raw) > ZIP_MAX:
        raise PhotoUnavailable("ZIP de fotos maior que o limite de segurança.")
    folder = CACHE / str(ano) / ue
    folder.mkdir(parents=True, exist_ok=True)
    wanted = {name.lower(): name for name in _candidate_names(ue, sq)}
    found: Path | None = None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size > FILE_MAX:
                    continue
                base = Path(info.filename).name
                if base.lower() not in wanted:
                    continue
                dest = folder / wanted[base.lower()]
                dest.write_bytes(zf.read(info))
                found = dest
                break
    except zipfile.BadZipFile as exc:
        raise PhotoUnavailable("ZIP de fotos oficial ilegível.") from exc
    if found is None:
        raise PhotoNotFound("Não há foto desta candidatura no ZIP oficial do TSE.")
    return found, "image/jpeg"
