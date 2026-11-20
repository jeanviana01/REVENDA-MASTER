"""Ponto de entrada para servidores de produção (ex.: gunicorn backend.wsgi:app)."""
from backend.app import create_app

app = create_app()
