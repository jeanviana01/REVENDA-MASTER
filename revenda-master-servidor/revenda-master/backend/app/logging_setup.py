"""Logs técnicos em console e arquivo rotativo. Nunca registramos senhas, tokens ou cookies."""
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(settings):
    root = logging.getLogger("revenda")
    if root.handlers:
        return root
    root.setLevel(logging.DEBUG if settings.env == "development" else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root.addHandler(stream)
    if settings.env != "test":
        try:
            os.makedirs(settings.log_dir, exist_ok=True)
            fh = RotatingFileHandler(os.path.join(settings.log_dir, "app.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            fh.setFormatter(fmt)
            root.addHandler(fh)
        except OSError:
            root.warning("Não foi possível criar o arquivo de log; usando só o console.")
    root.propagate = False
    return root


def safe(text, limit=40):
    """Texto vindo do usuário, limpo para log (sem quebras de linha nem caracteres de controle)."""
    return "".join(ch if ch.isprintable() else "?" for ch in str(text))[:limit]
