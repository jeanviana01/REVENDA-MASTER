import logging

from flask import Blueprint, current_app, g, jsonify, request

from ..db import get_db
from ..errors import ApiError
from ..logging_setup import safe
from ..services import vehicle_service
from .guards import admin_endpoint, json_body

bp = Blueprint("admin", __name__, url_prefix="/api/admin")
log = logging.getLogger("revenda.admin")


def _settings():
    return current_app.config["SETTINGS"]


@bp.post("/vehicles")
@admin_endpoint
def create_vehicle():
    vehicle = vehicle_service.create(get_db(), json_body())
    log.info("Veículo %s criado por %s", vehicle["id"], safe(g.user["username"]))
    return jsonify(vehicle), 201


@bp.put("/vehicles/<int:vehicle_id>")
@admin_endpoint
def update_vehicle(vehicle_id):
    vehicle = vehicle_service.update(get_db(), vehicle_id, json_body())
    log.info("Veículo %s alterado por %s", vehicle_id, safe(g.user["username"]))
    return jsonify(vehicle)


@bp.delete("/vehicles/<int:vehicle_id>")
@admin_endpoint
def delete_vehicle(vehicle_id):
    vehicle_service.delete(get_db(), _settings().upload_dir, vehicle_id)
    log.info("Veículo %s removido por %s", vehicle_id, safe(g.user["username"]))
    return "", 204


@bp.post("/vehicles/<int:vehicle_id>/photos")
@admin_endpoint
def upload_photo(vehicle_id):
    s = _settings()
    file = request.files.get("photo")
    if file is None:
        raise ApiError(400, "missing_file", "Envie a foto no campo 'photo'.")
    data = file.stream.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise ApiError(413, "file_too_large", f"A foto pode ter no máximo {s.max_upload_mb} MB.")
    vehicle = vehicle_service.add_photo(get_db(), s, vehicle_id, data)
    log.info("Foto adicionada ao veículo %s por %s", vehicle_id, safe(g.user["username"]))
    return jsonify(vehicle), 201


@bp.delete("/photos/<int:photo_id>")
@admin_endpoint
def delete_photo(photo_id):
    return jsonify(vehicle_service.remove_photo(get_db(), _settings().upload_dir, photo_id))


@bp.post("/photos/<int:photo_id>/main")
@admin_endpoint
def main_photo(photo_id):
    return jsonify(vehicle_service.make_main_photo(get_db(), photo_id))
