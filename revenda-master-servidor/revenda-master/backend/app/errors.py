"""Erros da API e tratamento centralizado. O cliente nunca recebe detalhes internos (stack trace, SQL, caminhos)."""
import logging
import uuid

from flask import jsonify, request
from werkzeug.exceptions import HTTPException

log = logging.getLogger("revenda.errors")

DEFAULT_MESSAGES = {
    400: "Requisição inválida.", 401: "É preciso entrar para continuar.", 403: "Você não tem permissão para isso.",
    404: "Não encontrado.", 405: "Método não permitido.", 413: "Arquivo ou conteúdo grande demais.",
    415: "Tipo de conteúdo não suportado.", 422: "Dados inválidos.", 429: "Muitas tentativas. Aguarde um pouco.",
}


class ApiError(Exception):
    def __init__(self, status, code, message=None, fields=None, headers=None):
        super().__init__(message or code)
        self.status, self.code, self.fields, self.headers = status, code, fields, headers or {}
        self.message = message or DEFAULT_MESSAGES.get(status, "Erro.")


class ValidationError(ApiError):
    def __init__(self, fields):
        super().__init__(422, "validation_error", "Alguns campos estão inválidos.", fields)


def _json_error(status, code, message, fields=None, headers=None):
    body = {"error": {"code": code, "message": message}}
    if fields:
        body["error"]["fields"] = fields
    resp = jsonify(body)
    resp.status_code = status
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp


def _is_api():
    return request.path.startswith("/api/")


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(e):
        return _json_error(e.status, e.code, e.message, e.fields, e.headers)

    @app.errorhandler(HTTPException)
    def handle_http(e):
        status = e.code or 500
        if _is_api():
            return _json_error(status, e.name.lower().replace(" ", "_"), DEFAULT_MESSAGES.get(status, "Erro."))
        page = f"<!doctype html><meta charset='utf-8'><title>{status}</title><p style='font-family:sans-serif'>" \
               f"{DEFAULT_MESSAGES.get(status, 'Erro.')} <a href='/'>Voltar ao início</a></p>"
        return page, status, {"Content-Type": "text/html; charset=utf-8"}

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        error_id = uuid.uuid4().hex[:10]
        log.exception("Erro inesperado [%s] %s %s", error_id, request.method, request.path)
        if _is_api():
            return _json_error(500, "internal_error", f"Erro interno. Código: {error_id}")
        return f"<!doctype html><meta charset='utf-8'><p>Erro interno. Código: {error_id}</p>", 500
