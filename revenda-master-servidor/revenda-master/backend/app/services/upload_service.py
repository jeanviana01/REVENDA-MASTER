"""Validação e gravação segura de fotos.

A imagem é aberta e regravada pelo Pillow: o arquivo original nunca é guardado, metadados (EXIF) somem,
o nome final é aleatório e só PNG/JPEG/WebP reais são aceitos (a extensão enviada não vale nada).
"""
import io
import re
import uuid
import warnings
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ..errors import ApiError

Image.MAX_IMAGE_PIXELS = 40_000_000                      # protege contra "bomba de descompressão"
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
MAX_SIDE = 1600
FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg)$")


def process_image(data: bytes):
    """Valida e normaliza a imagem. Devolve (bytes, extensão)."""
    if not data:
        raise ApiError(400, "empty_file", "Nenhum arquivo foi enviado.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)   # imagem gigante vira erro, não só aviso
            probe = Image.open(io.BytesIO(data))
            if probe.format not in ALLOWED_FORMATS:
                raise ApiError(415, "unsupported_image", "Envie uma imagem PNG, JPG ou WebP.")
            probe.verify()
            img = Image.open(io.BytesIO(data))
            img.load()
    except ApiError:
        raise
    except Image.DecompressionBombError:
        raise ApiError(413, "image_too_large", "A imagem tem dimensões grandes demais.")
    except (UnidentifiedImageError, Image.DecompressionBombWarning, OSError, SyntaxError, ValueError):
        raise ApiError(415, "invalid_image", "O arquivo não é uma imagem válida.")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    out = io.BytesIO()
    if has_alpha:
        img.convert("RGBA").save(out, format="PNG", optimize=True)
        return out.getvalue(), "png"
    img.convert("RGB").save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue(), "jpg"


def save_image(upload_dir, data: bytes):
    content, ext = process_image(data)
    directory = Path(upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    with open(directory / name, "xb") as fh:
        fh.write(content)
    return name


def delete_file(upload_dir, filename):
    if not FILENAME_RE.match(filename or ""):
        return
    try:
        (Path(upload_dir) / filename).unlink()
    except FileNotFoundError:
        pass
