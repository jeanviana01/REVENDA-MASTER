"""Acesso ao SQLite. Todas as consultas usam parâmetros (?) — nunca concatenação de texto."""
import sqlite3
from pathlib import Path

from flask import current_app, g

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["SETTINGS"].database_path)
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def run_migrations(path):
    """Aplica, em ordem, os arquivos .sql que ainda não foram aplicados."""
    conn = connect(path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))")
        done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if sql_file.name in done:
                continue
            conn.executescript(sql_file.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (sql_file.name,))
            conn.commit()
    finally:
        conn.close()
