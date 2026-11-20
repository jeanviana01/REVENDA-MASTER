import logging
import time

from flask import Blueprint, current_app, g, jsonify, request, session

from ..db import get_db
from ..errors import ApiError
from ..logging_setup import safe
from ..models import user as users
from ..security import new_csrf_token
from ..services import auth_service
from .guards import csrf_required, json_body, load_current_user, login_required

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
log = logging.getLogger("revenda.auth")


def _start_session(user):
    session.clear()
    session.permanent = True
    session["uid"], session["sv"], session["csrf"], session["iat"] = user["id"], user["session_version"], new_csrf_token(), int(time.time())


@bp.post("/login")
def login():
    data = json_body()
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_credentials_format", "Informe usuário e senha.")
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str) \
            or not username.strip() or not password or len(username) > 64 or len(password) > 128:
        raise ApiError(400, "invalid_credentials_format", "Informe usuário e senha.")
    s, limiter = current_app.config["SETTINGS"], current_app.extensions["limiter"]
    ip_key, user_key = ("login-ip", request.remote_addr), ("login-user", username.strip().lower())
    for key in (ip_key, user_key):
        blocked, retry = limiter.blocked(key, s.login_max_attempts, s.login_window_seconds)
        if blocked:
            log.warning("Login bloqueado por excesso de tentativas (ip=%s)", safe(request.remote_addr))
            raise ApiError(429, "too_many_attempts", "Muitas tentativas de login. Tente novamente mais tarde.", headers={"Retry-After": str(retry)})
    user = auth_service.authenticate(get_db(), username.strip(), password)
    if user is None:
        limiter.record(ip_key, s.login_window_seconds)
        limiter.record(user_key, s.login_window_seconds)
        log.warning("Falha de login (usuário=%s, ip=%s)", safe(username.strip()), safe(request.remote_addr))
        raise ApiError(401, "invalid_credentials", "Usuário ou senha incorretos.")
    limiter.reset(ip_key)
    limiter.reset(user_key)
    _start_session(user)
    log.info("Login realizado (usuário=%s)", safe(user["username"]))
    return jsonify({"authenticated": True, "username": user["username"], "csrf_token": session["csrf"]})


@bp.get("/me")
def me():
    user = load_current_user()
    if user is None:
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "username": user["username"], "csrf_token": session["csrf"]})


@bp.post("/logout")
@login_required
@csrf_required
def logout():
    users.bump_session(get_db(), g.user["id"])
    session.clear()
    return jsonify({"ok": True})


@bp.post("/password")
@login_required
@csrf_required
def change_password():
    data = json_body()
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_body", "Informe a senha atual e a nova.")
    current, new = data.get("current"), data.get("new")
    if not isinstance(current, str) or not isinstance(new, str):
        raise ApiError(400, "invalid_body", "Informe a senha atual e a nova.")
    user = auth_service.change_password(get_db(), g.user, current, new)
    _start_session(user)
    log.info("Senha alterada (usuário=%s)", safe(user["username"]))
    return jsonify({"ok": True, "csrf_token": session["csrf"]})
