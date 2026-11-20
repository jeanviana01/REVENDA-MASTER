"""Carrega o catálogo inicial (backend/seed/vehicles.json + fotos) no banco.

Uso:
    python backend/scripts/seed_catalog.py            # só carrega se o catálogo estiver vazio
    python backend/scripts/seed_catalog.py --force    # apaga os veículos atuais e recarrega
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.app.config import load_settings  # noqa: E402
from backend.app.db import connect, run_migrations  # noqa: E402
from backend.app.models import vehicle as repo  # noqa: E402
from backend.app.services import upload_service, vehicle_service  # noqa: E402

SEED_DIR = Path(__file__).resolve().parents[1] / "seed"


def seed(settings, force=False):
    run_migrations(settings.database_path)
    conn = connect(settings.database_path)
    try:
        existing = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        if existing and not force:
            return 0, f"O catálogo já tem {existing} veículos; nada foi alterado (use --force para recarregar)."
        if force:
            for row in conn.execute("SELECT filename FROM photos").fetchall():
                upload_service.delete_file(settings.upload_dir, row["filename"])
            conn.execute("DELETE FROM vehicles")
            conn.commit()
        items = json.loads((SEED_DIR / "vehicles.json").read_text(encoding="utf-8"))
        for item in items:
            clean = vehicle_service.validate_vehicle(item)
            vid = repo.insert(conn, clean)
            for photo in item.get("photos", []):
                name = upload_service.save_image(settings.upload_dir, (SEED_DIR / "images" / photo).read_bytes())
                repo.add_photo(conn, vid, name)
        return len(items), f"{len(items)} veículos carregados."
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    _, message = seed(load_settings(), force=args.force)
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
