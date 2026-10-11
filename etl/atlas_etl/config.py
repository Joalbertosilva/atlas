import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    download_dir: Path
    manifest_path: Path
    chunk_rows: int
    http_timeout: float
    http_retries: int
    download_concurrency: int


def _psycopg_url(url: str) -> str:
    # SQLAlchemy usa "postgresql+psycopg://"; psycopg aceita apenas "postgresql://".
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def load_settings() -> Settings:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL não definido (ver .env.example)")
    manifest_dir = Path(os.environ.get("ATLAS_MANIFEST_DIR", ROOT / "data" / "manifests"))
    return Settings(
        database_url=_psycopg_url(url),
        download_dir=Path(os.environ.get("ATLAS_DOWNLOAD_DIR", ROOT / "data" / "downloads")),
        manifest_path=manifest_dir / "tse_2026.yaml",
        chunk_rows=int(os.environ.get("ATLAS_CHUNK_ROWS", "250000")),
        http_timeout=float(os.environ.get("ATLAS_HTTP_TIMEOUT", "60")),
        http_retries=int(os.environ.get("ATLAS_HTTP_RETRIES", "5")),
        download_concurrency=max(1, min(4, int(os.environ.get("ATLAS_DOWNLOAD_CONCURRENCY", "2")))),
    )
