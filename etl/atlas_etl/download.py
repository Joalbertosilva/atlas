"""Download com timeout, retries com backoff exponencial, retomada via Range e hash."""
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from .manifest import Resource

log = logging.getLogger(__name__)
USER_AGENT = "AtlasEleitoral2026-ETL/0.1 (projeto independente; dados abertos TSE/IBGE)"


def head(client: httpx.Client, url: str) -> dict:
    r = client.head(url, follow_redirects=True)
    lm = r.headers.get("last-modified")
    return {
        "status": r.status_code,
        "content_length": int(r.headers["content-length"]) if r.headers.get("content-length") else None,
        "last_modified": parsedate_to_datetime(lm).isoformat() if lm else None,
    }


def sha256_file(path: Path) -> str:
    """SHA-256 com cache em arquivo lateral invalidado por tamanho+mtime."""
    side = path.with_name(path.name + ".sha256.json")
    st = path.stat()
    if side.exists():
        meta = json.loads(side.read_text())
        if meta.get("size") == st.st_size and meta.get("mtime") == st.st_mtime:
            return meta["sha256"]
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    digest = h.hexdigest()
    side.write_text(json.dumps({"size": st.st_size, "mtime": st.st_mtime, "sha256": digest}))
    return digest


def download(res: Resource, dest_dir: Path, *, timeout: float, retries: int, force: bool = False) -> dict:
    dest = dest_dir / res.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    meta_path = dest.with_name(dest.name + ".http.json")
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=20), headers={"User-Agent": USER_AGENT}) as client:
        info = head(client, res.url)
        if info["status"] in (405, 501):  # API do IBGE não aceita HEAD
            info = {"status": None, "content_length": None, "last_modified": None}
        elif info["status"] != 200:
            raise RuntimeError(f"{res.key}: HEAD retornou HTTP {info['status']}")
        if dest.exists() and not force:
            old = json.loads(meta_path.read_text()) if meta_path.exists() else None
            same_size = info["content_length"] is not None and dest.stat().st_size == info["content_length"]
            if old is None and same_size:
                # baixado por outra ferramenta: registra metadados sem baixar de novo
                meta_path.write_text(json.dumps({**info, "url": res.url, "downloaded_at": None}, indent=2))
                return {"key": res.key, "path": str(dest), "skipped": True, **info}
            if old is not None and old.get("last_modified") == info["last_modified"] and (
                    info["content_length"] is None or same_size):
                log.info("%s: já baixado e inalterado", res.key)
                return {"key": res.key, "path": str(dest), "skipped": True, **info}
        attempt = 0
        while True:
            attempt += 1
            try:
                offset = part.stat().st_size if part.exists() else 0
                headers = {"Range": f"bytes={offset}-"} if offset else {}
                with client.stream("GET", res.url, headers=headers, follow_redirects=True) as r:
                    if r.status_code == 200 and offset:
                        offset = 0  # servidor ignorou Range: recomeça
                    elif r.status_code not in (200, 206):
                        raise RuntimeError(f"HTTP {r.status_code}")
                    with part.open("ab" if offset else "wb") as f:
                        for chunk in r.iter_bytes(1 << 20):
                            f.write(chunk)
                size = part.stat().st_size
                if info["content_length"] and size != info["content_length"]:
                    raise RuntimeError(f"tamanho {size} != content-length {info['content_length']}")
                part.replace(dest)
                break
            except (httpx.HTTPError, RuntimeError) as exc:
                if attempt > retries:
                    raise RuntimeError(f"{res.key}: falhou após {retries} tentativas: {exc}") from exc
                wait = min(120, 2 ** attempt)
                log.warning("%s: tentativa %d falhou (%s); nova tentativa em %ss", res.key, attempt, exc, wait)
                time.sleep(wait)
    meta = {**info, "url": res.url, "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    meta_path.write_text(json.dumps(meta, indent=2))
    meta["sha256"] = sha256_file(dest)
    return {"key": res.key, "path": str(dest), "skipped": False, **meta}


def download_many(resources: list[Resource], dest_dir: Path, *, timeout: float, retries: int,
                  concurrency: int, force: bool = False) -> list[dict]:
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(download, r, dest_dir, timeout=timeout, retries=retries, force=force): r
                   for r in resources}
        for fut, res in futures.items():
            try:
                results.append(fut.result())
            except Exception as exc:  # noqa: BLE001 - registra e continua com os demais
                log.error("%s: %s", res.key, exc)
                results.append({"key": res.key, "error": str(exc)})
    return results


def http_metadata(path: Path) -> dict:
    meta_path = path.with_name(path.name + ".http.json")
    return json.loads(meta_path.read_text()) if meta_path.exists() else {}
