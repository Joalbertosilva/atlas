"""CLI `atlas-etl`: descobrir, baixar, inspecionar, importar, retomar, reconciliar e consultar cobertura."""
import argparse
import json
import logging
import sys
import time

import httpx

from . import aggregates, db, loaders, reconcile
from .config import load_settings
from .download import USER_AGENT, download_many, head
from .manifest import Resource, by_key, load_manifest
from .zipsafe import list_members

log = logging.getLogger("atlas_etl")

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
       "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
UES = ["BR"] + UFS
CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id="

# Ordem de dependência: referências -> candidaturas -> munzona -> agregados -> locais -> seções -> pesquisas.
KINDS = ["municipio_tse_ibge", "geometry", "consulta_vagas", "consulta_cand", "detalhe_munzona", "munzona_cand",
         "munzona_partido", "aggregates", "locais", "secao", "detalhe_secao", "pesquisas"]


def expected_scopes(kind: str) -> list[str]:
    return {
        "municipio_tse_ibge": ["ref:municipio_tse_ibge"],
        "geometry": ["geo:municipio", "geo:uf"],
        "consulta_vagas": ["ref:consulta_vagas"],
        "consulta_cand": [f"cand:{u}" for u in UES],
        "detalhe_munzona": [f"munzona_detalhe:{u}" for u in UES],
        "munzona_cand": [f"munzona_cand:{u}" for u in UES],
        "munzona_partido": [f"munzona_partido:{u}" for u in UES],
        "locais": [f"locais:{u}" for u in UFS + ["ZZ"]],
        "secao": [f"secao:{u}" for u in UES + ["ZZ"]],
        "detalhe_secao": [f"detalhe_secao:{u}" for u in UES + ["ZZ"]],
        "pesquisas": ["polls:BRASIL"],
    }.get(kind, [])


def _resources(settings) -> dict[str, Resource]:
    return by_key(load_manifest(settings.manifest_path))


def _path(settings, res: Resource):
    return settings.download_dir / res.filename


def _ensure_downloaded(settings, resources: list[Resource]) -> None:
    missing = [r for r in resources if not _path(settings, r).exists()]
    if missing:
        log.info("baixando %d recurso(s) ausente(s)", len(missing))
        for out in download_many(missing, settings.download_dir, timeout=settings.http_timeout,
                                 retries=settings.http_retries, concurrency=settings.download_concurrency):
            if "error" in out:
                raise SystemExit(f"download falhou: {out}")


def cmd_discover(settings, args) -> int:
    resources = list(_resources(settings).values())
    catalog_urls: set[str] = set()
    with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
        for ds in sorted({r.dataset for r in resources if not r.dataset.startswith("ibge")}):
            try:
                pkg = client.get(CKAN + ds).json()["result"]
                urls = {x["url"] for x in pkg["resources"]}
                catalog_urls |= urls
                print(f"[catálogo] {ds}: {len(urls)} recursos, metadata_modified={pkg.get('metadata_modified')}, "
                      f"licença={pkg.get('license_title')}")
            except Exception as exc:  # noqa: BLE001
                print(f"[catálogo] {ds}: API indisponível ({exc}); usando manifesto")
        for r in resources:
            if args.kind and r.kind != args.kind:
                continue
            try:
                h = head(client, r.url)
            except httpx.HTTPError as exc:
                h = {"status": f"erro {exc}"}
            listed = "sim" if r.url in catalog_urls else ("n/a" if r.dataset.startswith("ibge") else "NÃO")
            print(f"{r.key:45s} HTTP {h.get('status')} tamanho={h.get('content_length')} "
                  f"modificado={h.get('last_modified')} no_catálogo={listed}")
    return 0


def cmd_list(settings, args) -> int:
    for r in _resources(settings).values():
        p = _path(settings, r)
        print(f"{r.key:45s} {r.kind:20s} {'baixado' if p.exists() else '-':8s} {r.url}")
    return 0


def _select(settings, kind: str | None, ue: str | None) -> list[Resource]:
    out = []
    for r in _resources(settings).values():
        if kind and r.kind != kind:
            continue
        if ue and r.ue and r.ue != ue:
            continue
        out.append(r)
    return out


def cmd_download(settings, args) -> int:
    res = _select(settings, args.kind, args.ue)
    results = download_many(res, settings.download_dir, timeout=settings.http_timeout, retries=settings.http_retries,
                            concurrency=settings.download_concurrency, force=args.force)
    for r in results:
        print(json.dumps(r, ensure_ascii=False, default=str))
    return 1 if any("error" in r for r in results) else 0


def cmd_inspect(settings, args) -> int:
    res = _resources(settings)[args.key]
    path = _path(settings, res)
    _ensure_downloaded(settings, [res])
    for m in list_members(path):
        if args.member and args.member not in m.name:
            continue
        header = db.read_header(path, m.name)
        row = db.first_row(path, m.name)
        print(f"== {m.name}  crc32={m.crc32} bytes={m.size}")
        print(f"   encoding=ISO-8859-1 separador=';' colunas={len(header)}")
        for c in header:
            print(f"   {c:40s} {'' if row is None else str(row.get(c))[:60]}")
    return 0


def _import_kind(conn, settings, kind: str, ue: str | None, force: bool) -> list[dict]:
    R = _resources(settings)
    ck = settings.chunk_rows
    out: list[dict] = []

    def need(key):
        r = R[key]
        _ensure_downloaded(settings, [r])
        return r, _path(settings, r)

    if kind == "municipio_tse_ibge":
        r, p = need("municipio_tse_ibge")
        out.append(loaders.load_tse_ibge(conn, r, p, chunk_rows=ck, force=force))
    elif kind == "geometry":
        r, p = need("ibge_malha_municipios_minima")
        out.append(loaders.load_geometry(conn, r, p, "municipio", force=force))
        r, p = need("ibge_malha_ufs_minima")
        out.append(loaders.load_geometry(conn, r, p, "uf", force=force))
    elif kind == "consulta_vagas":
        r, p = need("consulta_vagas_2026")
        out.append(loaders.load_vagas(conn, r, p, chunk_rows=ck, force=force))
    elif kind == "pesquisas":
        r, p = need("pesquisa_eleitoral_2026")
        out.append(loaders.load_polls(conn, r, p, chunk_rows=ck, force=force))
    elif kind == "aggregates":
        out.append({"scope": "aggregates", "status": "rebuilt", **aggregates.rebuild(conn)})
    else:
        table = {
            "consulta_cand": ("consulta_cand_2026", loaders.load_candidates, UES),
            "detalhe_munzona": ("detalhe_votacao_munzona_2026", loaders.load_detalhe_munzona, UES),
            "munzona_cand": ("votacao_candidato_munzona_2026", loaders.load_munzona_cand, UES),
            "munzona_partido": ("votacao_partido_munzona_2026", loaders.load_munzona_partido, UES),
            "locais": ("eleitorado_local_votacao_2026", loaders.load_locais, UFS + ["ZZ"]),
            "detalhe_secao": ("detalhe_votacao_secao_2026", loaders.load_detalhe_secao, UES + ["ZZ"]),
        }
        if kind == "secao":
            for u in [ue] if ue else UES + ["ZZ"]:
                r, p = need(f"votacao_secao_2026_{u}")
                out.append(loaders.load_secao(conn, r, p, u, chunk_rows=ck, force=force))
            aggregates.analyze_sections(conn)
        elif kind in table:
            key, fn, ues = table[kind]
            r, p = need(key)
            for u in [ue] if ue else ues:
                out.append(fn(conn, r, p, u, chunk_rows=ck, force=force))
            if kind == "detalhe_secao":
                aggregates.analyze_sections(conn)
        else:
            raise SystemExit(f"tipo desconhecido: {kind}")
    return out


def cmd_import(settings, args) -> int:
    conn = db.connect(settings.database_url)
    t0 = time.time()
    results = _import_kind(conn, settings, args.kind, args.ue, args.force)
    for r in results:
        print(json.dumps(r, ensure_ascii=False, default=str))
    print(f"tempo total: {time.time() - t0:.1f}s")
    return 1 if any(r.get("status") == "failed" for r in results) else 0


def cmd_import_all(settings, args) -> int:
    conn = db.connect(settings.database_url)
    kinds = [k for k in KINDS if k not in (args.skip or [])]
    if args.only:
        kinds = [k for k in kinds if k in args.only]
    failed = 0
    for kind in kinds:
        t0 = time.time()
        log.info("=== %s", kind)
        for r in _import_kind(conn, settings, kind, None, args.force):
            failed += r.get("status") == "failed"
            print(json.dumps(r, ensure_ascii=False, default=str), flush=True)
        log.info("=== %s concluído em %.1fs", kind, time.time() - t0)
    print(f"kinds_done falhas_parciais: {failed}", flush=True)
    # Agregados já foram reconstruídos no kind "aggregates" (munzona).
    # Este segundo rebuild só é necessário se secao/detalhe_secao/locais
    # rodaram depois; detalhe_secao e locais não alimentam agg.*.
    if "aggregates" in kinds and "secao" in kinds:
        aggregates.rebuild(conn)
    print(f"falhas: {failed}", flush=True)
    return 1 if failed else 0


def cmd_resume(settings, args) -> int:
    """Reexecuta somente recortes ainda não publicados ou cuja última tentativa falhou."""
    conn = db.connect(settings.database_url)
    published = {r[0] for r in conn.execute("SELECT scope_key FROM meta.publication").fetchall()}
    pending = []
    for kind in KINDS:
        for scope in expected_scopes(kind):
            if scope not in published:
                pending.append((kind, scope))
    if not pending:
        print("nada pendente")
        return 0
    failed = 0
    for kind, scope in pending:
        ue = scope.split(":", 1)[1] if ":" in scope and kind not in ("municipio_tse_ibge", "consulta_vagas",
                                                                      "pesquisas") else None
        if kind == "geometry":
            ue = None
        log.info("retomando %s", scope)
        for r in _import_kind(conn, settings, kind, ue, False):
            failed += r.get("status") == "failed"
            print(json.dumps(r, ensure_ascii=False, default=str), flush=True)
    aggregates.rebuild(conn)
    return 1 if failed else 0


def cmd_reconcile(settings, args) -> int:
    conn = db.connect(settings.database_url)
    results = reconcile.run_all(conn, settings.download_dir)
    bad = [r for r in results if not r["ok"]]
    print(f"verificações: {len(results)}  ok: {len(results) - len(bad)}  divergências: {len(bad)}")
    for r in bad[: args.show]:
        print("DIVERGÊNCIA", json.dumps(r, ensure_ascii=False))
    return 0


def cmd_rebuild(settings, args) -> int:
    conn = db.connect(settings.database_url)
    print(json.dumps(aggregates.rebuild(conn)))
    return 0


def cmd_coverage(settings, args) -> int:
    conn = db.connect(settings.database_url)
    pub = {r[0]: r[1:] for r in conn.execute(
        """SELECT p.scope_key, p.rows_published, r.source_generated_at, p.published_at
           FROM meta.publication p JOIN meta.import_run r ON r.id = p.import_run_id""").fetchall()}
    failed = {r[0]: r[1] for r in conn.execute(
        """SELECT DISTINCT ON (scope_key) scope_key, error FROM meta.import_run
           WHERE status = 'failed' ORDER BY scope_key, id DESC""").fetchall()}
    for kind in KINDS:
        scopes = expected_scopes(kind)
        if not scopes:
            continue
        done = [s for s in scopes if s in pub]
        print(f"{kind:20s} {len(done):3d}/{len(scopes):3d} recortes publicados")
        if args.verbose:
            for s in scopes:
                if s in pub:
                    rows, gen, at = pub[s]
                    print(f"   {s:28s} linhas={rows:>10,} gerado_tse={gen} publicado={at:%Y-%m-%d %H:%M}")
                else:
                    print(f"   {s:28s} PENDENTE {('falha: ' + failed[s][:120]) if s in failed else ''}")
    return 0


def cmd_cleanup(settings, args) -> int:
    conn = db.connect(settings.database_url)
    tables = [r[0] for r in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'staging' AND tablename LIKE 'run\\_%'").fetchall()]
    for t in tables:
        db.drop_staging(conn, t)
    conn.execute("DELETE FROM app.search_cache WHERE expires_at < now()")
    conn.commit()
    print(f"staging removidas: {len(tables)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="atlas-etl", description="ETL do Atlas Eleitoral 2026 (TSE/IBGE)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("discover", help="compara manifesto com a API CKAN e HEAD do CDN")
    s.add_argument("--kind")
    sub.add_parser("list", help="lista recursos do manifesto")
    s = sub.add_parser("download", help="baixa recursos (concorrência limitada, retry e retomada)")
    s.add_argument("--kind")
    s.add_argument("--ue")
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("inspect", help="mostra membros, cabeçalho e primeira linha de um recurso")
    s.add_argument("key")
    s.add_argument("--member")
    s = sub.add_parser("import", help="importa um tipo (opcionalmente um recorte --ue)")
    s.add_argument("kind", choices=KINDS)
    s.add_argument("--ue", choices=UES + ["ZZ"])
    s.add_argument("--force", action="store_true", help="reimporta mesmo se idêntico ao publicado")
    s = sub.add_parser("import-all", help="pipeline nacional completo, na ordem de dependência")
    s.add_argument("--skip", nargs="*", choices=KINDS)
    s.add_argument("--only", nargs="*", choices=KINDS)
    s.add_argument("--force", action="store_true")
    sub.add_parser("resume", help="retoma recortes pendentes ou que falharam")
    s = sub.add_parser("reconcile", help="executa verificações de totais")
    s.add_argument("--show", type=int, default=40)
    sub.add_parser("rebuild-aggregates", help="reconstrói agregados e executa ANALYZE")
    s = sub.add_parser("coverage", help="mostra recortes publicados e pendentes")
    s.add_argument("-v", "--verbose", action="store_true")
    sub.add_parser("cleanup", help="remove staging órfã e cache expirado")
    args = p.parse_args(argv)
    settings = load_settings()
    return {
        "discover": cmd_discover, "list": cmd_list, "download": cmd_download, "inspect": cmd_inspect,
        "import": cmd_import, "import-all": cmd_import_all, "resume": cmd_resume, "reconcile": cmd_reconcile,
        "rebuild-aggregates": cmd_rebuild, "coverage": cmd_coverage, "cleanup": cmd_cleanup,
    }[args.cmd](settings, args)


if __name__ == "__main__":
    sys.exit(main())
