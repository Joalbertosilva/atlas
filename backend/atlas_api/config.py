import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    searxng_url: str
    search_timeout: float
    search_cache_ttl: int
    search_rate_limit: int
    cache_secret: bytes
    cors_origins: list[str]


def load_config() -> Config:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL não definido")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    secret = os.environ.get("API_CACHE_SECRET") or os.environ.get("SEARXNG_SECRET")
    if not secret:
        raise RuntimeError("API_CACHE_SECRET não definido")
    return Config(
        database_url=url,
        searxng_url=os.environ.get("SEARXNG_URL", "http://searxng:8080").rstrip("/"),
        search_timeout=float(os.environ.get("SEARCH_TIMEOUT_SECONDS", "8")),
        search_cache_ttl=int(os.environ.get("SEARCH_CACHE_TTL_SECONDS", "600")),
        search_rate_limit=int(os.environ.get("SEARCH_RATE_LIMIT_PER_MINUTE", "20")),
        cache_secret=secret.encode(),
        cors_origins=[o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()],
    )
