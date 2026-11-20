"""Auxiliares dos testes: app com banco temporário, imagens de teste e login."""
import io
import os
import tempfile

from PIL import Image

from backend.app import create_app
from backend.app.db import connect
from backend.app.services import auth_service

ADMIN_USER = "admin_teste"
ADMIN_PASS = "SenhaForte2026x"

VEHICLE = {"brand": "Chevrolet", "model": "Onix LT", "version": "", "year": 2020, "year_label": "", "color": "Azul",
           "transmission": "Manual", "description": "Hatch compacto · Motor 1.0 Flex.", "available": True, "sections": []}


def make_app(tmp=None, **overrides):
    tmp = tmp or tempfile.mkdtemp(prefix="rm-test-")
    base = {"env": "test", "secret_key": "x" * 40, "database_path": os.path.join(tmp, "t.sqlite3"),
            "upload_dir": os.path.join(tmp, "uploads"), "log_dir": os.path.join(tmp, "logs"),
            "whatsapp_number": "5511999999999", "cookie_secure": False}
    base.update(overrides)
    app = create_app(base)
    conn = connect(app.config["SETTINGS"].database_path)
    try:
        auth_service.create_or_reset(conn, ADMIN_USER, ADMIN_PASS)
    finally:
        conn.close()
    return app


def png_bytes(size=(40, 24), color=(200, 30, 30, 255), mode="RGBA", fmt="PNG"):
    buf = io.BytesIO()
    Image.new(mode, size, color if mode == "RGBA" else color[:3]).save(buf, format=fmt)
    return buf.getvalue()


def login(client, username=ADMIN_USER, password=ADMIN_PASS):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    return r, (r.get_json() or {}).get("csrf_token")


def hdr(token):
    return {"X-CSRF-Token": token}
