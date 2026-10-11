"""Ciclo de vida de importações: idempotência por impressão digital e publicação por recorte."""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg

from .download import http_metadata, sha256_file
from .manifest import Resource
from .zipsafe import Member


@dataclass
class Run:
    id: int
    scope_key: str
    resource: Resource
    member: Member
    path: Path


def register_resource(conn: psycopg.Connection, res: Resource, path: Path | None) -> None:
    meta = http_metadata(path) if path else {}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO meta.resource (resource_key, dataset, kind, url, listed_in_catalog, license, description,
                                       http_last_modified, content_length, checked_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
            ON CONFLICT (resource_key) DO UPDATE SET
              url = EXCLUDED.url, listed_in_catalog = EXCLUDED.listed_in_catalog, license = EXCLUDED.license,
              description = EXCLUDED.description,
              http_last_modified = COALESCE(EXCLUDED.http_last_modified, meta.resource.http_last_modified),
              content_length = COALESCE(EXCLUDED.content_length, meta.resource.content_length),
              checked_at = now()
            """,
            (res.key, res.dataset, res.kind, res.url, res.listed_in_catalog, res.license, res.description,
             meta.get("last_modified"), meta.get("content_length")),
        )
    conn.commit()


def parse_generated(row: dict | None) -> datetime | None:
    if not row:
        return None
    d, h = row.get("DT_GERACAO"), row.get("HH_GERACAO")
    try:
        return datetime.strptime(f"{d} {h}", "%d/%m/%Y %H:%M:%S")
    except (TypeError, ValueError):
        return None


def published_fingerprint(conn: psycopg.Connection, scope_key: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT r.fingerprint FROM meta.publication p JOIN meta.import_run r ON r.id = p.import_run_id
               WHERE p.scope_key = %s""",
            (scope_key,),
        )
        row = cur.fetchone()
    return row[0] if row else None


def begin(conn: psycopg.Connection, res: Resource, path: Path, member: Member, scope_key: str,
          generated_at: datetime | None, force: bool = False) -> Run | None:
    """Retorna None quando o mesmo conteúdo já está publicado para o recorte (idempotência)."""
    fingerprint = f"{member.name}:{member.crc32}:{member.size}"
    if not force and published_fingerprint(conn, scope_key) == fingerprint:
        return None
    meta = http_metadata(path)
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO meta.import_run (resource_key, member_name, scope_key, zip_sha256, member_crc32,
                   member_size, source_generated_at, http_last_modified, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'running') RETURNING id""",
            (res.key, member.name, scope_key, sha256_file(path), member.crc32, member.size, generated_at,
             meta.get("last_modified")),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return Run(run_id, scope_key, res, member, path)


def fail(conn: psycopg.Connection, run: Run, error: str) -> None:
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE meta.import_run SET status='failed', error=%s, finished_at=now() WHERE id=%s",
            (error[:4000], run.id),
        )
    conn.commit()


def publish(cur: psycopg.Cursor, run: Run, kind: str, sg_uf: str | None, rows_read: int, rows_loaded: int,
            validation: dict) -> None:
    """Executado DENTRO da transação que substitui os fatos do recorte."""
    cur.execute(
        """UPDATE meta.import_run SET status='superseded'
           WHERE id = (SELECT import_run_id FROM meta.publication WHERE scope_key=%s) AND id <> %s""",
        (run.scope_key, run.id),
    )
    cur.execute(
        """INSERT INTO meta.publication (scope_key, kind, sg_uf, import_run_id, rows_published, published_at)
           VALUES (%s,%s,%s,%s,%s, now())
           ON CONFLICT (scope_key) DO UPDATE SET import_run_id=EXCLUDED.import_run_id,
             rows_published=EXCLUDED.rows_published, published_at=now(), kind=EXCLUDED.kind, sg_uf=EXCLUDED.sg_uf""",
        (run.scope_key, kind, sg_uf, run.id, rows_loaded),
    )
    cur.execute(
        """UPDATE meta.import_run SET status='published', rows_read=%s, rows_loaded=%s, validation=%s,
                  finished_at=now() WHERE id=%s""",
        (rows_read, rows_loaded, json.dumps(validation, default=str), run.id),
    )
