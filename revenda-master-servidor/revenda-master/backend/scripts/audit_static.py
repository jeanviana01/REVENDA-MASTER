"""Verificações estáticas de segurança do código (não substitui um scanner de dependências como pip-audit).

Uso: python backend/scripts/audit_static.py   (sai com código 1 se encontrar algo)
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND, FRONTEND = ROOT / "backend" / "app", ROOT / "frontend"
DANGEROUS_BUILTINS = {"eval", "exec", "compile", "__import__"}                        # chamadas diretas: eval(...)
DANGEROUS_ATTRS = {"system", "popen", "Popen", "check_output", "render_template_string"}   # os.system(...), subprocess.Popen(...)
DANGEROUS_MODULES = {"pickle", "marshal", "subprocess", "shelve", "yaml"}
JS_PATTERNS = {r"\binnerHTML\b": "innerHTML", r"\bouterHTML\b": "outerHTML", r"insertAdjacentHTML": "insertAdjacentHTML",
               r"document\.write": "document.write", r"\beval\s*\(": "eval()", r"new\s+Function\s*\(": "new Function()",
               r"setTimeout\s*\(\s*['\"]": "setTimeout com texto", r"localStorage|sessionStorage": "armazenamento no navegador"}
SECRET_PATTERNS = [r"(?i)(password|passwd|senha|secret|token|api[_-]?key)\s*[:=]\s*['\"][^'\"\s]{6,}['\"]", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
                   r"AKIA[0-9A-Z]{16}", r"scrypt\$\d+\$"]
ALLOWED_EXTERNAL = ("fonts.googleapis.com", "fonts.gstatic.com", "wa.me", "www.google.com", "www.w3.org")


def iter_files(base, suffixes):
    return [p for p in base.rglob("*") if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts]


def audit():
    findings, notes = [], []
    for path in iter_files(BACKEND, {".py"}):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(ROOT)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for m in mods:
                    if m.split(".")[0] in DANGEROUS_MODULES:
                        findings.append(f"{rel}:{node.lineno}: importa módulo sensível '{m}'")
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if (isinstance(node.func, ast.Name) and name in DANGEROUS_BUILTINS) or (isinstance(node.func, ast.Attribute) and name in DANGEROUS_ATTRS):
                    findings.append(f"{rel}:{node.lineno}: chamada sensível '{name}()'")
                if name == "execute" and node.args:
                    arg = node.args[0]
                    if isinstance(arg, (ast.JoinedStr, ast.BinOp)):
                        findings.append(f"{rel}:{node.lineno}: SQL montado com f-string/concatenação direto no execute()")
                    elif isinstance(arg, ast.Name):
                        notes.append(f"{rel}:{node.lineno}: execute({arg.id}) com variável — revisar: só pode conter texto fixo + '?'")
        text = path.read_text(encoding="utf-8")
        for pat in SECRET_PATTERNS[:3]:
            for m in re.finditer(pat, text):
                findings.append(f"{rel}: possível segredo no código: {m.group(0)[:30]}…")

    for path in iter_files(FRONTEND, {".js"}):
        text = re.sub(r"/\*.*?\*/|(?<!:)//[^\n]*", "", path.read_text(encoding="utf-8"), flags=re.S)   # ignora comentários
        for pat, label in JS_PATTERNS.items():
            if re.search(pat, text):
                findings.append(f"{path.relative_to(ROOT)}: uso de {label}")
        for pat in SECRET_PATTERNS:
            for m in re.finditer(pat, text):
                findings.append(f"{path.relative_to(ROOT)}: possível segredo no front-end: {m.group(0)[:30]}…")
    for path in iter_files(FRONTEND, {".html"}):
        text, rel = path.read_text(encoding="utf-8"), path.relative_to(ROOT)
        if re.search(r"<script(?![^>]*\bsrc=)[^>]*>", text):
            findings.append(f"{rel}: script inline (viola a CSP)")
        if re.search(r"\son[a-z]+\s*=", text):
            findings.append(f"{rel}: manipulador de evento inline (onclick etc.)")
        if re.search(r"<[a-z]+[^>]*\sstyle\s*=", text):
            findings.append(f"{rel}: atributo style inline (viola a CSP)")
        for url in re.findall(r"""(?:src|href)=["'](https?://[^"']+)["']""", text):
            if not any(host in url for host in ALLOWED_EXTERNAL):
                findings.append(f"{rel}: recurso externo não previsto: {url}")
        for url in re.findall(r"""<script[^>]+src=["'](https?://[^"']+)["']""", text):
            findings.append(f"{rel}: script externo: {url}")
    for path in iter_files(FRONTEND, {".css"}):
        for url in re.findall(r"url\((https?://[^)]+)\)", path.read_text(encoding="utf-8")):
            findings.append(f"{path.relative_to(ROOT)}: CSS carrega recurso externo: {url}")

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").exists() else ""
    for needed in (".env", "instance/", "*.sqlite3"):
        if needed not in gitignore:
            findings.append(f".gitignore não protege '{needed}'")
    if not (ROOT / ".env.example").exists():
        findings.append(".env.example ausente")
    else:
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
            if re.match(r"(?i)\s*(SECRET_KEY|ADMIN_PASSWORD)\s*=\s*\S+", line) and not re.search(r"troque|change|example|exemplo", line, re.I):
                findings.append(f".env.example parece conter valor real: {line.split('=')[0]}")
    if (ROOT / ".env").exists():
        notes.append(".env existe nesta pasta (ok localmente; nunca envie ao Git).")
    return findings, notes


def main():
    findings, notes = audit()
    for n in notes:
        print("nota:", n)
    for f in findings:
        print("ACHADO:", f)
    print(f"\n{len(findings)} achado(s), {len(notes)} nota(s) para revisão manual.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
