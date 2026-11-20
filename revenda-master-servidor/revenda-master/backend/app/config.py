"""Configuração da aplicação, lida de variáveis de ambiente (.env no servidor).

Nenhum segredo fica no código. Em produção a aplicação se recusa a iniciar com
uma SECRET_KEY ausente, fraca ou igual ao exemplo.
"""
import os
import secrets
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]          # raiz do projeto
PLACEHOLDER_SECRETS = {"", "change-me", "troque-esta-chave", "troque-por-uma-chave-longa-e-aleatoria"}
ENVIRONMENTS = ("development", "test", "production")

# Fabricantes aceitos no cadastro (cada um tem logo no front-end)
BRANDS = ("Chevrolet", "Volkswagen", "Fiat", "Jeep", "Hyundai", "Toyota", "Honda", "Renault")
TRANSMISSIONS = ("Manual", "Automático")


class ConfigError(RuntimeError):
    pass


def _env_bool(name, default):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "sim", "on")


def _env_int(name, default, minimum=0):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} precisa ser um número inteiro") from exc
    if value < minimum:
        raise ConfigError(f"{name} precisa ser >= {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    env: str
    secret_key: str
    database_path: str
    upload_dir: str
    frontend_dir: str
    log_dir: str
    max_upload_mb: int
    max_photos_per_vehicle: int
    session_hours: int
    cookie_secure: bool
    whatsapp_number: str
    store_address: str
    allowed_origins: tuple
    login_max_attempts: int
    login_window_seconds: int
    trust_proxy_hops: int

    @property
    def is_production(self):
        return self.env == "production"


def load_settings(overrides=None):
    """Monta as configurações. `overrides` é usado pelos testes."""
    load_dotenv(BASE_DIR / ".env")                      # não sobrescreve variáveis já definidas
    env = os.getenv("APP_ENV", "development").strip().lower()
    if env not in ENVIRONMENTS:
        raise ConfigError(f"APP_ENV deve ser um de {ENVIRONMENTS}")

    secret = os.getenv("SECRET_KEY", "").strip()
    if env == "production":
        if secret in PLACEHOLDER_SECRETS or len(secret) < 32:
            raise ConfigError("Em produção, defina SECRET_KEY com pelo menos 32 caracteres aleatórios.")
    elif secret in PLACEHOLDER_SECRETS:
        secret = secrets.token_hex(32)                  # chave temporária: as sessões caem ao reiniciar

    origins = tuple(o.strip().rstrip("/") for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip())
    settings = Settings(
        env=env,
        secret_key=secret,
        database_path=os.getenv("DATABASE_PATH", str(BASE_DIR / "instance" / f"{env}.sqlite3")),
        upload_dir=os.getenv("UPLOAD_DIR", str(BASE_DIR / "instance" / f"uploads-{env}")),
        frontend_dir=str(BASE_DIR / "frontend"),
        log_dir=os.getenv("LOG_DIR", str(BASE_DIR / "instance" / "logs")),
        max_upload_mb=_env_int("MAX_UPLOAD_MB", 5, 1),
        max_photos_per_vehicle=_env_int("MAX_PHOTOS_PER_VEHICLE", 12, 1),
        session_hours=_env_int("SESSION_HOURS", 8, 1),
        cookie_secure=_env_bool("COOKIE_SECURE", env == "production"),
        whatsapp_number=os.getenv("WHATSAPP_NUMBER", "").strip(),
        store_address=os.getenv("STORE_ADDRESS", "Av. Imperial, 1200, Centro").strip(),
        allowed_origins=origins,
        login_max_attempts=_env_int("LOGIN_MAX_ATTEMPTS", 8, 1),
        login_window_seconds=_env_int("LOGIN_WINDOW_SECONDS", 900, 1),
        trust_proxy_hops=_env_int("TRUST_PROXY_HOPS", 0, 0),
    )
    if overrides:
        settings = replace(settings, **overrides)
    return settings
