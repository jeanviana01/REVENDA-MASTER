"""Teste de carga simples: sobe o servidor com banco temporário e dispara requisições simultâneas.

Uso: python backend/tests/perf/load_test.py [requisições_por_rota] [simultâneas]
Observação: usa o servidor de desenvolvimento (Werkzeug). Em produção use gunicorn/waitress; os números mudam.
"""
import json
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ROUTES = ["/", "/api/meta", "/api/vehicles", "/api/vehicles?brand=Chevrolet&transmission=Manual", "/api/vehicles/1", "/assets/css/site.css", "/assets/js/rm.js"]


def hit(url):
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            r.read()
            ok = r.status == 200
    except Exception:
        ok = False
    return ok, (time.perf_counter() - t) * 1000


def main(n=200, workers=20):
    tmp = tempfile.mkdtemp(prefix="rm-load-")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    env = dict(os.environ, APP_ENV="development", SECRET_KEY="load-" + "k" * 40, DATABASE_PATH=os.path.join(tmp, "l.sqlite3"),
               UPLOAD_DIR=os.path.join(tmp, "up"), LOG_DIR=os.path.join(tmp, "logs"), PORT=str(port), PYTHONPATH=ROOT)
    subprocess.run([sys.executable, os.path.join(ROOT, "backend", "scripts", "seed_catalog.py")], env=env, cwd=ROOT, check=True, capture_output=True)
    log = open(os.path.join(tmp, "server.out"), "w")
    server = subprocess.Popen([sys.executable, os.path.join(ROOT, "backend", "run.py")], env=env, cwd=ROOT, stdout=log, stderr=log)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=2).read(); break
            except Exception:
                time.sleep(0.25)
        results, worst_error_rate = [], 0.0
        print(f"{n} requisições por rota, {workers} simultâneas\n{'rota':58} {'ok':>6} {'p50':>8} {'p95':>8} {'máx':>8} {'req/s':>8}")
        for route in ROUTES:
            t0 = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as ex:
                out = list(ex.map(hit, [base + route] * n))
            total = time.perf_counter() - t0
            lat = sorted(x[1] for x in out); ok = sum(1 for x in out if x[0])
            p95 = lat[int(len(lat) * 0.95) - 1]
            worst_error_rate = max(worst_error_rate, 1 - ok / n)
            print(f"{route:58} {ok:>3}/{n:<3} {statistics.median(lat):7.1f}ms {p95:7.1f}ms {lat[-1]:7.1f}ms {n / total:8.0f}")
            results.append({"route": route, "ok": ok, "p50": statistics.median(lat), "p95": p95, "max": lat[-1], "rps": n / total})
        print("\ntaxa máxima de erro:", f"{worst_error_rate:.1%}")
        return results, worst_error_rate
    finally:
        server.terminate(); server.wait(timeout=10); log.close()


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:3]]
    _, err = main(*args)
    sys.exit(1 if err > 0 else 0)
