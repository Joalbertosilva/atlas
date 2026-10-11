"""Acesso ao banco: somente SQL parametrizado via sqlalchemy.text com bind params."""
from typing import Any

from flask import current_app, g
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def make_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        hide_parameters=True,  # parâmetros (ex.: consultas de busca) nunca vão para logs de erro
        connect_args={"options": "-c statement_timeout=20000 -c default_transaction_read_only=on",
                      "application_name": "atlas-api"},
    )


def make_write_engine(url: str) -> Engine:
    """Conexão separada, apenas para o cache de busca (app.search_cache)."""
    return create_engine(url, pool_size=2, max_overflow=2, pool_pre_ping=True, hide_parameters=True,
                         connect_args={"options": "-c statement_timeout=5000", "application_name": "atlas-api-cache"})


def _conn():
    if "db_conn" not in g:
        g.db_conn = current_app.extensions["atlas_engine"].connect()
    return g.db_conn


def close_conn(_exc=None) -> None:
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


def fetch_all(sql: str, **params: Any) -> list[dict]:
    return [dict(r._mapping) for r in _conn().execute(text(sql), params)]


def fetch_one(sql: str, **params: Any) -> dict | None:
    row = _conn().execute(text(sql), params).first()
    return None if row is None else dict(row._mapping)


def scalar(sql: str, **params: Any):
    return _conn().execute(text(sql), params).scalar()


def set_statement_timeout(seconds: int) -> None:
    ms = max(1000, int(seconds) * 1000)
    _conn().execute(text(f"SET LOCAL statement_timeout = {ms}"))
