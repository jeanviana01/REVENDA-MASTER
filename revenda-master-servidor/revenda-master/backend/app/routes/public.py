from flask import Blueprint, current_app, jsonify, request

from ..config import BRANDS, TRANSMISSIONS
from ..db import get_db
from ..errors import ApiError
from ..models import vehicle as repo
from ..services import vehicle_service

bp = Blueprint("public", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return jsonify({"status": "ok"})


@bp.get("/meta")
def meta():
    s = current_app.config["SETTINGS"]
    data = repo.meta(get_db())
    data.update({"brands": list(BRANDS), "transmissions": list(TRANSMISSIONS),
                 "whatsapp": s.whatsapp_number, "address": s.store_address})
    return jsonify(data)


@bp.get("/vehicles")
def list_vehicles():
    args = request.args
    filters = {}
    for key in ("brand", "model", "color", "transmission"):
        value = args.get(key, "").strip()
        if len(value) > 80:
            raise ApiError(400, "invalid_filter", f"Filtro '{key}' grande demais.")
        filters[key] = value
    year = args.get("year", "").strip()
    if year:
        if not year.isdigit() or len(year) > 4:
            raise ApiError(400, "invalid_filter", "Filtro 'year' precisa ser um ano.")
        filters["year"] = int(year)
    q = args.get("q", "").strip()
    if len(q) > 80:
        raise ApiError(400, "invalid_filter", "Busca grande demais.")
    items = repo.list_vehicles(get_db(), filters, q or None)
    return jsonify({"count": len(items), "items": items})


@bp.get("/vehicles/<int:vehicle_id>")
def vehicle_detail(vehicle_id):
    return jsonify(vehicle_service.detail(get_db(), vehicle_id))
