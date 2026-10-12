"""Atlas Eleitoral 2026 — API Flask somente leitura (exceto cache de busca)."""
import logging

from flask import Flask
from flask_cors import CORS
from flask_smorest import Api

from . import errors
from .config import Config, load_config
from .db import close_conn, make_engine, make_write_engine
from .search import SearchService


def create_app(config: Config | None = None, search_transport=None) -> Flask:
    cfg = config or load_config()
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.config.update(
        API_TITLE="Atlas Eleitoral 2026 API",
        API_VERSION="1.0.0",
        OPENAPI_VERSION="3.0.3",
        OPENAPI_URL_PREFIX="/api",
        OPENAPI_JSON_PATH="openapi.json",
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # sem log de acesso com consultas

    app.extensions["atlas_engine"] = make_engine(cfg.database_url)
    write_engine = make_write_engine(cfg.database_url)
    app.extensions["atlas_search"] = SearchService(cfg.searxng_url, cfg.search_timeout, cfg.search_cache_ttl,
                                                   cfg.cache_secret, write_engine, cfg.search_rate_limit,
                                                   transport=search_transport)
    app.teardown_appcontext(close_conn)
    if cfg.cors_origins:
        CORS(app, resources={r"/api/*": {"origins": cfg.cors_origins}}, methods=["GET", "POST"],
             allow_headers=["Content-Type"], supports_credentials=False)

    api = Api(app)
    from .routes import meta, results, search, territory
    for bp in (meta.blp, results.blp, territory.blp, search.blp):
        api.register_blueprint(bp)
    errors.register(app)

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        if resp.mimetype and resp.mimetype.startswith("image/"):
            resp.headers["Cache-Control"] = "public, max-age=86400"
        else:
            resp.headers.setdefault("Cache-Control", "no-store")
        if resp.mimetype in ("application/json", "application/geo+json", "text/csv"):
            resp.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return resp

    return app
