"""Entrega do front-end e das fotos enviadas."""
from flask import Blueprint, abort, current_app, send_from_directory

from ..services.upload_service import FILENAME_RE

bp = Blueprint("pages", __name__)


def _front():
    return current_app.config["SETTINGS"].frontend_dir


@bp.get("/")
def home():
    return send_from_directory(_front(), "index.html")


@bp.get("/veiculo")
def vehicle_page():
    return send_from_directory(_front(), "veiculo.html")


@bp.get("/admin")
def admin_page():
    return send_from_directory(_front(), "admin.html")


@bp.get("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(f"{_front()}/assets", filename, max_age=3600)   # impede sair da pasta (../)


@bp.get("/uploads/<filename>")
def uploads(filename):
    if not FILENAME_RE.match(filename):
        abort(404)
    resp = send_from_directory(current_app.config["SETTINGS"].upload_dir, filename, max_age=86400, conditional=True)
    resp.headers["Content-Security-Policy"] = "default-src 'none'"
    return resp
