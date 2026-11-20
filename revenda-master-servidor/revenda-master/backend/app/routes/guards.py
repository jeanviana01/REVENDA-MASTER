"""Decoradores de proteção: login, CSRF e limite de requisições de escrita."""
from functools import wraps

from flask import current_app, g, request, session

from ..db import get_db
from ..errors import ApiError
from ..models import user as users
from ..security import csrf_matches

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def load_current_user():
    uid, version = session.get("uid"), session.get("sv")
    if not uid:
        return None
    user = users.get_by_id(get_db(), uid)
    if user is None or user["session_version"] != version:   # sessão antiga/invalidada (logout, senha trocada)
        session.clear()
        return None
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = load_current_user()
        if user is None:
            raise ApiError(401, "not_authenticated", "É preciso entrar para continuar.")
        g.user = user
        return view(*args, **kwargs)
    return wrapper


def csrf_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method not in SAFE_METHODS and not csrf_matches(session.get("csrf"), request.headers.get("X-CSRF-Token")):
            raise ApiError(403, "csrf_failed", "Sessão expirada ou requisição inválida. Recarregue a página.")
        return view(*args, **kwargs)
    return wrapper


def rate_limited_write(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method not in SAFE_METHODS:
            ok, retry = current_app.extensions["limiter"].hit(("write", g.user["id"]), 120, 60)
            if not ok:
                raise ApiError(429, "rate_limited", headers={"Retry-After": str(retry)})
        return view(*args, **kwargs)
    return wrapper


def admin_endpoint(view):
    """Login + CSRF + limite de escrita, nesta ordem."""
    return login_required(csrf_required(rate_limited_write(view)))


def json_body():
    if not request.is_json:
        raise ApiError(415, "json_required", "Envie os dados em JSON (Content-Type: application/json).")
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError(400, "invalid_json", "JSON inválido.")
    return data
