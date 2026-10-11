from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

CODES = {400: "invalid_parameter", 404: "not_found", 405: "method_not_allowed", 422: "invalid_parameter",
         429: "rate_limited", 503: "upstream_unavailable"}
MESSAGES = {400: "Parâmetros inválidos.", 404: "Recurso não encontrado.", 405: "Método não permitido.",
            422: "Parâmetros inválidos.", 429: "Limite de requisições excedido. Tente novamente em instantes.",
            503: "Serviço temporariamente indisponível."}


class ApiError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.status, self.message, self.code, self.details = status, message, code or CODES.get(status, "error"), details


def error_body(status: int, message: str, code: str | None = None, details: dict | None = None):
    return jsonify({"error": {"code": code or CODES.get(status, "error"), "message": message,
                              "details": details or {}}}), status


def register(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api(e: ApiError):
        return error_body(e.status, e.message, e.code, e.details)

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        details = {}
        data = getattr(e, "data", None)
        if isinstance(data, dict) and "messages" in data:
            details = data["messages"]
        elif isinstance(data, dict) and "errors" in data:
            details = data["errors"]
        return error_body(e.code or 500, MESSAGES.get(e.code or 500, e.description or "Erro."), None, details)

    @app.errorhandler(Exception)
    def _any(e: Exception):
        app.logger.exception("erro interno: %s", type(e).__name__)
        return error_body(500, "Erro interno.", "internal_error")
