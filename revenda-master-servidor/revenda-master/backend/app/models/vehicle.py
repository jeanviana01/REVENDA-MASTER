"""Consultas de veículos e fotos (sempre com parâmetros)."""
import json

FILTER_COLUMNS = {"brand": "brand", "model": "model", "year": "year", "color": "color", "transmission": "transmission"}


def _like_escape(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def photos_of(db, vehicle_id):
    return db.execute("SELECT id, filename, position FROM photos WHERE vehicle_id = ? ORDER BY position, id", (vehicle_id,)).fetchall()


def to_dict(row, photos=None, detail=False):
    photos = photos if photos is not None else []
    data = {
        "id": row["id"], "brand": row["brand"], "model": row["model"], "version": row["version"],
        "year": row["year"], "year_label": row["year_label"], "color": row["color"],
        "transmission": row["transmission"], "description": row["description"],
        "available": bool(row["available"]),
        "photo": f"/uploads/{photos[0]['filename']}" if photos else None,
    }
    if detail:
        data["sections"] = json.loads(row["sections"] or "[]")
        data["photos"] = [{"id": p["id"], "url": f"/uploads/{p['filename']}", "main": i == 0} for i, p in enumerate(photos)]
    return data


def list_vehicles(db, filters, q=None):
    where, params = [], []
    for key, column in FILTER_COLUMNS.items():
        if filters.get(key) not in (None, ""):
            where.append(f"{column} = ?")                   # nome da coluna vem da lista fixa acima
            params.append(filters[key])
    if q:
        like = f"%{_like_escape(q)}%"
        where.append("(brand LIKE ? ESCAPE '\\' OR model LIKE ? ESCAPE '\\' OR version LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')")
        params += [like, like, like, like]
    sql = "SELECT * FROM vehicles" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY brand, model, year DESC, id"
    rows = db.execute(sql, params).fetchall()
    first_photos = {}
    for r in db.execute("SELECT vehicle_id, filename FROM photos ORDER BY position, id"):
        first_photos.setdefault(r["vehicle_id"], [r])
    return [to_dict(r, first_photos.get(r["id"], [])) for r in rows]


def get_vehicle(db, vehicle_id):
    row = db.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    return row


def insert(db, d):
    cur = db.execute(
        "INSERT INTO vehicles (brand, model, version, year, year_label, color, transmission, description, sections, available) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (d["brand"], d["model"], d["version"], d["year"], d["year_label"], d["color"], d["transmission"],
         d["description"], json.dumps(d["sections"], ensure_ascii=False), int(d["available"])))
    db.commit()
    return cur.lastrowid


def update(db, vehicle_id, d):
    db.execute(
        "UPDATE vehicles SET brand=?, model=?, version=?, year=?, year_label=?, color=?, transmission=?, description=?, "
        "sections=?, available=?, updated_at=datetime('now') WHERE id=?",
        (d["brand"], d["model"], d["version"], d["year"], d["year_label"], d["color"], d["transmission"],
         d["description"], json.dumps(d["sections"], ensure_ascii=False), int(d["available"]), vehicle_id))
    db.commit()


def delete(db, vehicle_id):
    db.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
    db.commit()


def meta(db):
    rows = db.execute("SELECT brand, model FROM vehicles GROUP BY brand, model ORDER BY brand, model").fetchall()
    models = {}
    for r in rows:
        models.setdefault(r["brand"], []).append(r["model"])
    return {
        "models_by_brand": models,
        "years": [r[0] for r in db.execute("SELECT DISTINCT year FROM vehicles ORDER BY year DESC")],
        "colors": [r[0] for r in db.execute("SELECT DISTINCT color FROM vehicles WHERE color <> '' ORDER BY color")],
    }


# ---- fotos ----
def add_photo(db, vehicle_id, filename):
    pos = db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM photos WHERE vehicle_id = ?", (vehicle_id,)).fetchone()[0]
    cur = db.execute("INSERT INTO photos (vehicle_id, filename, position) VALUES (?, ?, ?)", (vehicle_id, filename, pos))
    db.commit()
    return cur.lastrowid


def count_photos(db, vehicle_id):
    return db.execute("SELECT COUNT(*) FROM photos WHERE vehicle_id = ?", (vehicle_id,)).fetchone()[0]


def get_photo(db, photo_id):
    return db.execute("SELECT id, vehicle_id, filename, position FROM photos WHERE id = ?", (photo_id,)).fetchone()


def delete_photo(db, photo_id):
    db.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    db.commit()


def set_main_photo(db, vehicle_id, photo_id):
    ids = [p["id"] for p in photos_of(db, vehicle_id)]
    ordered = [photo_id] + [i for i in ids if i != photo_id]
    for pos, pid in enumerate(ordered):
        db.execute("UPDATE photos SET position = ? WHERE id = ?", (pos, pid))
    db.commit()
