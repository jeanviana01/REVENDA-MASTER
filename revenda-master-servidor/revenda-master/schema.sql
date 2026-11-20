-- Esquema inicial do banco (SQLite). Aplicado automaticamente na inicialização.
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT    NOT NULL,
    session_version INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE vehicles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    brand        TEXT    NOT NULL,
    model        TEXT    NOT NULL,
    version      TEXT    NOT NULL DEFAULT '',
    year         INTEGER NOT NULL CHECK (year BETWEEN 1980 AND 2100),
    year_label   TEXT    NOT NULL DEFAULT '',
    color        TEXT    NOT NULL DEFAULT '',
    transmission TEXT    NOT NULL CHECK (transmission IN ('Manual', 'Automático')),
    description  TEXT    NOT NULL DEFAULT '',
    sections     TEXT    NOT NULL DEFAULT '[]',
    available    INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_vehicles_brand        ON vehicles (brand);
CREATE INDEX idx_vehicles_year         ON vehicles (year);
CREATE INDEX idx_vehicles_color        ON vehicles (color);
CREATE INDEX idx_vehicles_transmission ON vehicles (transmission);

CREATE TABLE photos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles (id) ON DELETE CASCADE,
    filename   TEXT    NOT NULL UNIQUE,
    position   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_photos_vehicle ON photos (vehicle_id, position);
