"""CSV oficial (ZIP) -> tabela UNLOGGED de staging via COPY, em chunks com pandas."""
import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg
from psycopg import sql

from .zipsafe import open_member

log = logging.getLogger(__name__)
ENCODING = "latin-1"  # confirmado: arquivos do TSE 2026 são ISO-8859-1, separador ';', CRLF
SEP = ";"


class LayoutError(ValueError):
    pass


@dataclass
class StageResult:
    table: str
    rows: int
    source_generated_at: datetime | None
    header: list[str]


def read_header(zip_path: Path, member: str) -> tuple[list[str], list[str] | None]:
    z, f = open_member(zip_path, member)
    try:
        text = io.TextIOWrapper(f, encoding=ENCODING, newline="")
        reader = csv.reader(text, delimiter=SEP, quotechar='"')
        header = next(reader)
        first = next(reader, None)
        return header, first
    finally:
        f.close()
        z.close()


def _generated_at(header: list[str], first: list[str] | None) -> datetime | None:
    if not first or "DT_GERACAO" not in header or "HH_GERACAO" not in header:
        return None
    try:
        d = first[header.index("DT_GERACAO")]
        h = first[header.index("HH_GERACAO")]
        return datetime.strptime(f"{d} {h}", "%d/%m/%Y %H:%M:%S")
    except (ValueError, IndexError):
        return None


def staging_table(run_id: int, kind: str) -> str:
    return f"run_{run_id}_{kind}"


def stage_csv(conn: psycopg.Connection, run_id: int, kind: str, zip_path: Path, member: str,
              columns: list[str], chunk_rows: int) -> StageResult:
    header, first = read_header(zip_path, member)
    missing = [c for c in columns if c not in header]
    if missing:
        raise LayoutError(f"{member}: colunas ausentes no layout: {missing}")
    table = staging_table(run_id, kind)
    ident = sql.Identifier("staging", table)
    cols_sql = sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c.lower())) for c in columns)
    with conn.cursor() as cur:
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(ident))
        cur.execute(sql.SQL("CREATE UNLOGGED TABLE {} ({})").format(ident, cols_sql))
    conn.commit()

    copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv)").format(
        ident, sql.SQL(", ").join(sql.Identifier(c.lower()) for c in columns))
    rows = 0
    z, f = open_member(zip_path, member)
    try:
        reader = pd.read_csv(f, sep=SEP, encoding=ENCODING, dtype=str, keep_default_na=False,
                             na_filter=False, usecols=columns, chunksize=chunk_rows, quotechar='"')
        with conn.cursor() as cur, cur.copy(copy_stmt) as cp:
            for chunk in reader:
                buf = io.StringIO()
                chunk[columns].to_csv(buf, header=False, index=False)
                cp.write(buf.getvalue())
                rows += len(chunk)
                if rows % (chunk_rows * 8) == 0:
                    log.info("%s: %s linhas em staging", member, f"{rows:,}")
    finally:
        f.close()
        z.close()
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(sql.SQL("ANALYZE {}").format(ident))
    conn.commit()
    return StageResult(f"staging.{table}", rows, _generated_at(header, first), header)


def drop_staging(conn: psycopg.Connection, table: str) -> None:
    schema, name = table.split(".", 1)
    with conn.cursor() as cur:
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(schema, name)))
    conn.commit()
