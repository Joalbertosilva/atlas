"""Conexão, staging com COPY em chunks e utilidades SQL."""
import io
import logging
import re
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import psycopg
from psycopg import sql

from .zipsafe import open_member

log = logging.getLogger(__name__)
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def connect(url: str) -> psycopg.Connection:
    conn = psycopg.connect(url, autocommit=False, application_name="atlas-etl")
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        cur.execute("SET work_mem = '128MB'")
    conn.commit()
    return conn


def read_header(path: Path, member: str) -> list[str]:
    z, f = open_member(path, member)
    try:
        first = f.readline().decode("latin-1").strip()
    finally:
        f.close()
        z.close()
    return [c.strip('"') for c in first.split(";")]


def first_row(path: Path, member: str) -> dict[str, str] | None:
    z, f = open_member(path, member)
    try:
        df = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str, keep_default_na=False, nrows=1)
    finally:
        f.close()
        z.close()
    return None if df.empty else df.iloc[0].to_dict()


def require_columns(header: list[str], required: Iterable[str], member: str) -> None:
    missing = [c for c in required if c not in header]
    if missing:
        raise ValueError(f"{member}: layout inesperado, colunas ausentes: {missing}")


def stage_csv(conn: psycopg.Connection, table: str, path: Path, member: str, columns: list[str],
              chunk_rows: int) -> int:
    """Cria staging.<table> (UNLOGGED, colunas texto) e carrega as colunas selecionadas via COPY.

    Leitura com pandas em chunks (dtype=str, sem conversão de NA), encoding ISO-8859-1 e
    separador ';' confirmados nos arquivos reais de 2026.
    """
    if not _IDENT.match(table):
        raise ValueError(f"nome de staging inválido: {table}")
    header = read_header(path, member)
    require_columns(header, columns, member)
    cols_sql = sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c.lower())) for c in columns)
    ident = sql.Identifier("staging", table)
    with conn.cursor() as cur:
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(ident))
        cur.execute(sql.SQL("CREATE UNLOGGED TABLE {} ({})").format(ident, cols_sql))
    conn.commit()
    copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, FORCE_NOT_NULL ({}))").format(
        ident,
        sql.SQL(", ").join(sql.Identifier(c.lower()) for c in columns),
        sql.SQL(", ").join(sql.Identifier(c.lower()) for c in columns),
    )
    total = 0
    z, f = open_member(path, member)
    try:
        reader = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str, keep_default_na=False,
                             usecols=columns, chunksize=chunk_rows, quotechar='"')
        with conn.cursor() as cur, cur.copy(copy_stmt) as cp:
            for chunk in reader:
                buf = io.StringIO()
                chunk[columns].to_csv(buf, header=False, index=False)
                cp.write(buf.getvalue())
                total += len(chunk)
                if total % (chunk_rows * 8) == 0:
                    log.info("  %s: %d linhas em staging", member, total)
    finally:
        f.close()
        z.close()
    conn.commit()
    return total


def drop_staging(conn: psycopg.Connection, table: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier("staging", table)))
    conn.commit()


def scalar(conn: psycopg.Connection, query, params=None):
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return None if row is None else row[0]
