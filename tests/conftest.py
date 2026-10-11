"""Fixtures. Dados sintéticos só aqui e em tests/synthetic/ — nunca no ETL de produção."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "etl"))


def _host_database_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip()
    if not url:
        return None
    return url.replace("@db:5432", "@127.0.0.1:55432")


@pytest.fixture(scope="session")
def database_url():
    url = _host_database_url()
    if not url:
        pytest.skip("DATABASE_URL não definido")
    return url


@pytest.fixture
def cache_secret():
    return b"test-cache-secret-not-for-production"
