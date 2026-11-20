"""Regras de negócio dos veículos: validação dos dados e operações."""
import re

from ..config import BRANDS, TRANSMISSIONS
from ..errors import ApiError, ValidationError
from ..models import vehicle as repo
from . import upload_service

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _clean(value, field, errors, max_len, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        errors[field] = "Precisa ser um texto."
        return ""
    value = _CONTROL.sub("", value).strip()
    if required and not value:
        errors[field] = "Campo obrigatório."
    elif len(value) > max_len:
        errors[field] = f"Use no máximo {max_len} caracteres."
    return value


def validate_vehicle(payload):
    """Valida e limpa os dados de um veículo. Levanta ValidationError com os campos errados."""
    if not isinstance(payload, dict):
        raise ApiError(400, "invalid_body", "Envie um objeto JSON.")
    errors = {}
    brand = _clean(payload.get("brand"), "brand", errors, 40, True)
    if brand and brand not in BRANDS:
        errors["brand"] = "Fabricante inválido."
    model = _clean(payload.get("model"), "model", errors, 80, True)
    version = _clean(payload.get("version"), "version", errors, 60)
    year = payload.get("year")
    if isinstance(year, str) and year.strip().isdigit():
        year = int(year.strip())
    if isinstance(year, bool) or not isinstance(year, int) or not 1980 <= year <= 2100:
        errors["year"] = "Informe um ano entre 1980 e 2100."
    year_label = _clean(payload.get("year_label"), "year_label", errors, 20)
    color = _clean(payload.get("color"), "color", errors, 30)
    transmission = payload.get("transmission")
    if transmission not in TRANSMISSIONS:
        errors["transmission"] = "Escolha Manual ou Automático."
    description = _clean(payload.get("description"), "description", errors, 300)
    available = payload.get("available", True)
    if not isinstance(available, bool):
        errors["available"] = "Precisa ser verdadeiro ou falso."
    sections = _validate_sections(payload.get("sections", []), errors)
    if errors:
        raise ValidationError(errors)
    return {"brand": brand, "model": model, "version": version, "year": year, "year_label": year_label, "color": color,
            "transmission": transmission, "description": description, "available": available, "sections": sections}


def _validate_sections(raw, errors):
    if raw in (None, ""):
        return []
    if not isinstance(raw, list) or len(raw) > 10:
        errors["sections"] = "Use no máximo 10 blocos de detalhes."
        return []
    clean = []
    for sec in raw:
        if not isinstance(sec, dict) or not isinstance(sec.get("items", []), list) or len(sec.get("items", [])) > 20:
            errors["sections"] = "Cada bloco precisa de título e até 20 itens."
            return []
        local = {}
        title = _clean(sec.get("title"), "title", local, 60, True)
        items = [_clean(i, "item", local, 200) for i in sec.get("items", [])]
        items = [i for i in items if i]
        if local:
            errors["sections"] = "Título (até 60) e itens (até 200 caracteres) precisam ser textos válidos."
            return []
        clean.append({"title": title, "items": items})
    return clean


def get_or_404(db, vehicle_id):
    row = repo.get_vehicle(db, vehicle_id)
    if row is None:
        raise ApiError(404, "vehicle_not_found", "Veículo não encontrado.")
    return row


def detail(db, vehicle_id):
    row = get_or_404(db, vehicle_id)
    return repo.to_dict(row, repo.photos_of(db, vehicle_id), detail=True)


def create(db, payload):
    vid = repo.insert(db, validate_vehicle(payload))
    return detail(db, vid)


def update(db, vehicle_id, payload):
    get_or_404(db, vehicle_id)
    repo.update(db, vehicle_id, validate_vehicle(payload))
    return detail(db, vehicle_id)


def delete(db, upload_dir, vehicle_id):
    get_or_404(db, vehicle_id)
    files = [p["filename"] for p in repo.photos_of(db, vehicle_id)]
    repo.delete(db, vehicle_id)                          # fotos saem do banco por ON DELETE CASCADE
    for name in files:
        upload_service.delete_file(upload_dir, name)


def add_photo(db, settings, vehicle_id, data):
    get_or_404(db, vehicle_id)
    if repo.count_photos(db, vehicle_id) >= settings.max_photos_per_vehicle:
        raise ApiError(409, "too_many_photos", f"Cada veículo aceita até {settings.max_photos_per_vehicle} fotos.")
    name = upload_service.save_image(settings.upload_dir, data)
    try:
        repo.add_photo(db, vehicle_id, name)
    except Exception:
        upload_service.delete_file(settings.upload_dir, name)
        raise
    return detail(db, vehicle_id)


def remove_photo(db, upload_dir, photo_id):
    photo = repo.get_photo(db, photo_id)
    if photo is None:
        raise ApiError(404, "photo_not_found", "Foto não encontrada.")
    repo.delete_photo(db, photo_id)
    upload_service.delete_file(upload_dir, photo["filename"])
    return detail(db, photo["vehicle_id"])


def make_main_photo(db, photo_id):
    photo = repo.get_photo(db, photo_id)
    if photo is None:
        raise ApiError(404, "photo_not_found", "Foto não encontrada.")
    repo.set_main_photo(db, photo["vehicle_id"], photo_id)
    return detail(db, photo["vehicle_id"])
