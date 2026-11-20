"""Fábrica da aplicação Revenda Master (Flask)."""
import logging
from datetime import timedelta
from pathlib import Path

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import load_settings
from .db import close_db, run_migrations
from .errors import ApiError, register_error_handlers
from .logging_setup import setup_logging
from .routes import admin, auth, pages, public
from .security import RateLimiter, apply_security_headers, origin_allowed

UNSAFE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def create_app(overrides=None):
    settings = load_settings(overrides)
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SETTINGS=settings,
        SECRET_KEY=settings.secret_key,
        MAX_CONTENT_LENGTH=(settings.max_upload_mb + 1) * 1024 * 1024,
        SESSION_COOKIE_NAME="rm_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=settings.cookie_secure,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=settings.session_hours),
    )
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    setup_logging(settings)
    log = logging.getLogger("revenda")
    if settings.is_production and not settings.cookie_secure:
        log.warning("COOKIE_SECURE está desligado em produção: o cookie de sessão pode trafegar sem HTTPS.")
    run_migrations(settings.database_path)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    app.extensions["limiter"] = RateLimiter()
    if settings.trust_proxy_hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=settings.trust_proxy_hops, x_proto=settings.trust_proxy_hops, x_host=settings.trust_proxy_hops)

    for module in (pages, public, auth, admin):
        app.register_blueprint(module.bp)
    register_error_handlers(app)
    app.teardown_appcontext(close_db)

    @app.before_request
    def check_origin():
        # Defesa extra contra CSRF: se o navegador informa a origem, ela precisa ser a do próprio site.
        if request.path.startswith("/api/") and request.method in UNSAFE_METHODS:
            origin = request.headers.get("Origin")
            if origin and not origin_allowed(origin, request.host, settings.allowed_origins):
                raise ApiError(403, "origin_not_allowed", "Origem não permitida.")

    @app.after_request
    def add_headers(response):
        apply_security_headers(response, request.is_secure, request.path.startswith("/api/"))
        origin = request.headers.get("Origin")
        if origin and origin in settings.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers.add("Vary", "Origin")
        return response

    return app
