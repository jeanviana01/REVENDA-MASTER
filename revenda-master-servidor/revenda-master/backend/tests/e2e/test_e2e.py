"""Testes ponta a ponta (navegador real) contra o servidor de verdade, com banco e fotos temporários.

Requer:  pip install playwright  &&  python -m playwright install chromium
Rodar:   python -m unittest backend.tests.e2e.test_e2e -v
"""
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import json

from PIL import Image

try:
    from playwright.sync_api import sync_playwright
except ImportError:                                             # pragma: no cover
    sync_playwright = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ADMIN_USER, ADMIN_PASS = "admin_e2e", "SenhaE2E-2026x"
WHATS = "5511999999999"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def api(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


@unittest.skipIf(sync_playwright is None, "playwright não instalado")
class E2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="rm-e2e-")
        cls.port = free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        env = dict(os.environ, APP_ENV="development", SECRET_KEY="e2e-" + "k" * 40, DATABASE_PATH=os.path.join(cls.tmp, "e2e.sqlite3"),
                   UPLOAD_DIR=os.path.join(cls.tmp, "uploads"), LOG_DIR=os.path.join(cls.tmp, "logs"), WHATSAPP_NUMBER=WHATS,
                   ADMIN_USERNAME=ADMIN_USER, ADMIN_PASSWORD=ADMIN_PASS, PORT=str(cls.port), PYTHONPATH=ROOT)
        for script in ("seed_catalog.py", "create_admin.py"):
            subprocess.run([sys.executable, os.path.join(ROOT, "backend", "scripts", script)], env=env, cwd=ROOT, check=True, capture_output=True)
        cls.log = open(os.path.join(cls.tmp, "server.out"), "w")
        cls.server = subprocess.Popen([sys.executable, os.path.join(ROOT, "backend", "run.py")], env=env, cwd=ROOT, stdout=cls.log, stderr=cls.log)
        for _ in range(60):
            try:
                if api(cls.base, "/api/health")["status"] == "ok":
                    break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("servidor não subiu")
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.photo = os.path.join(cls.tmp, "carro-teste.png")
        Image.new("RGBA", (300, 160), (20, 120, 220, 255)).save(cls.photo)
        cls.photo2 = os.path.join(cls.tmp, "carro-teste2.png")
        Image.new("RGBA", (300, 160), (220, 120, 20, 255)).save(cls.photo2)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.server.terminate(); cls.server.wait(timeout=10); cls.log.close()

    def setUp(self):
        self.ctx = self.browser.new_context(viewport={"width": 1100, "height": 900})
        # sem internet no ambiente de teste: as fontes externas são respondidas vazias
        self.ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda r: r.fulfill(status=200, body="", content_type="text/css"))
        self.page = self.ctx.new_page()
        self.errors, self.failed = [], []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.page.on("requestfailed", lambda r: self.failed.append(r.url))
        self.page.on("dialog", lambda d: d.accept())

    def tearDown(self):
        self.ctx.close()

    def wait_js(self, page, expr, timeout=15000):
        """Espera uma condição JS ficar verdadeira. (O wait_for_function do Playwright usa eval, que a CSP do site bloqueia de propósito.)"""
        end = time.time() + timeout / 1000
        while time.time() < end:
            if page.evaluate("() => !!(" + expr + ")"):
                return
            time.sleep(0.1)
        raise AssertionError(f"condição não satisfeita: {expr}")

    def ready(self, page=None):
        """Espera os botões de fabricante serem montados (ficam dentro de um painel fechado, por isso 'attached')."""
        (page or self.page).wait_for_selector("#marcas button", state="attached")

    def go(self, path="/"):
        self.page.goto(self.base + path, wait_until="load")

    def assertClean(self):
        self.assertEqual(self.errors, [], f"erros no console: {self.errors}")
        self.assertEqual([f for f in self.failed if "/uploads/" not in f or "forcar-falha" in f], [], f"requisições falhas: {self.failed}")

    # ---------------- página inicial ----------------
    def test_home_media_and_layout(self):
        self.go()
        self.ready()
        self.assertEqual(self.page.locator("#marcas button").count(), 8)
        self.assertGreater(self.page.evaluate("document.querySelector('.logo img').naturalWidth"), 0)
        self.wait_js(self.page, "document.getElementById('video-onix').readyState >= 2")
        self.assertIsNone(self.page.evaluate("document.getElementById('video-onix').error && document.getElementById('video-onix').error.code"))
        self.assertTrue(self.page.is_visible("#btn-fabricantes")); self.assertTrue(self.page.is_visible("#btn-buscar"))
        self.assertTrue(self.page.is_visible("#btn-zap")); self.assertIn(f"wa.me/{WHATS}", self.page.get_attribute("#btn-zap", "href"))
        self.assertIn("google.com/maps", self.page.get_attribute("#btn-maps", "href"))
        self.assertClean()

    def test_every_brand_lists_the_catalog_with_working_photos_and_toggles(self):
        self.go(); self.ready(); self.page.click("#btn-fabricantes")
        total = 0
        for brand in api(self.base, "/api/meta")["brands"]:
            expected = api(self.base, "/api/vehicles?brand=" + brand)["items"]
            self.page.click(f'#marcas button:has-text("{brand}")')
            if expected:
                self.page.wait_for_selector("#lista-marca .carro")
                self.assertEqual(self.page.locator("#lista-marca .carro").count(), len(expected))
                total += len(expected)
                self.wait_js(self.page, "[...document.querySelectorAll('#lista-marca .thumb')].every(i => i.complete && i.naturalWidth > 0)")
                names = self.page.eval_on_selector_all("#lista-marca .carro strong", "els => els.map(e => e.textContent)")
                self.assertTrue(all(brand in n for n in names))
                self.assertEqual(self.page.locator("#lista-marca .selo").first.text_content(), "Disponível para venda")
            else:
                self.page.wait_for_selector("#lista-marca a.btn")
                self.assertIn("Nenhum", self.page.inner_text("#lista-marca"))
                self.assertIn("wa.me/", self.page.get_attribute("#lista-marca a.btn", "href"))
            self.page.click(f'#marcas button:has-text("{brand}")')                       # segundo clique: fecha
            self.assertEqual(self.page.locator("#lista-marca > *").count(), 0)
            self.assertEqual(self.page.get_attribute(f'#marcas button:has-text("{brand}")', "aria-pressed"), "false")
        self.assertEqual(total, api(self.base, "/api/vehicles")["count"])
        self.assertClean()

    def test_search_filters_match_the_api_and_not_found_flow(self):
        self.go(); self.ready(); self.page.click("#btn-buscar")
        def search(**f):
            for sel, key in (("#sel-marca", "brand"), ("#sel-ano", "year"), ("#sel-cor", "color"), ("#sel-cambio", "transmission")):
                self.page.select_option(sel, f.get(key, ""))
            self.page.select_option("#sel-modelo", f.get("model", ""))
            self.page.click("#form-busca button[type=submit]")
            self.wait_js(self.page, "!document.getElementById('resultado').textContent.includes('Buscando')")
        search()
        self.assertIn("pelo menos uma opção", self.page.inner_text("#resultado"))
        for f in ({"color": "Cinza"}, {"transmission": "Manual"}, {"brand": "Fiat"}, {"year": "2022"}, {"brand": "Volkswagen", "transmission": "Automático"}):
            search(**f)
            qs = "&".join(f"{k}={v}" for k, v in f.items())
            expected = api(self.base, "/api/vehicles?" + urllib.request.quote(qs, safe="=&"))["count"]
            self.assertGreater(expected, 0, f)
            self.assertEqual(self.page.locator("#resultado .carro").count(), expected, f)
        search(brand="Hyundai", color="Preto")
        self.assertIn("Que pena que não temos disponível no momento.", self.page.inner_text("#resultado"))
        href = self.page.get_attribute("#resultado a.btn", "href")
        self.assertIn(f"wa.me/{WHATS}", href); self.assertIn("Hyundai", href); self.assertIn("preto", href)
        self.page.select_option("#sel-marca", "Chevrolet")
        models = self.page.eval_on_selector_all("#sel-modelo option", "els => els.filter(e => e.value).map(e => e.textContent)")
        self.assertEqual(sorted(models), sorted(api(self.base, "/api/meta")["models_by_brand"]["Chevrolet"]))
        self.assertClean()

    def test_detail_page(self):
        self.go(); self.ready(); self.page.click("#btn-fabricantes"); self.page.click('#marcas button:has-text("Volkswagen")')
        self.page.click('#lista-marca a.carro:has-text("Virtus")')
        self.page.wait_for_selector("h1.vei-titulo")
        self.assertIn("/veiculo?id=", self.page.url)
        self.assertIn("Virtus Exclusive", self.page.inner_text("h1.vei-titulo"))
        self.wait_js(self.page, "document.querySelector('.vei-vitrine img').complete && document.querySelector('.vei-vitrine img').naturalWidth > 0")
        self.assertEqual(self.page.locator(".vei-bloco").count(), 3)
        self.assertIn("Porta-malas de 521 litros", self.page.inner_text(".vei-blocos"))
        self.assertIn("wa.me/", self.page.get_attribute(".vei-acoes a.btn.cheio", "href"))
        self.page.click(".vei-acoes a:has-text('Ver outros carros')"); self.ready()
        self.assertEqual(self.page.url, self.base + "/")
        self.assertClean()

    def test_detail_page_with_bad_ids_shows_message(self):
        for path in ("/veiculo?id=999999", "/veiculo?id=abc", "/veiculo", "/veiculo?id=1%27%20OR%201=1"):
            self.go(path); self.page.wait_for_selector(".estado.erro")
            self.assertIn("não encontrado", self.page.inner_text(".estado.erro"))
            self.page.click(".vei-voltar"); self.ready()
        self.assertEqual([e for e in self.errors if "404" not in e], [])

    # ---------------- responsividade ----------------
    def test_responsive_no_horizontal_overflow(self):
        for w, h in ((360, 740), (390, 844), (768, 1024), (1366, 768), (1920, 1080)):
            self.page.set_viewport_size({"width": w, "height": h})
            self.go(); self.ready(); self.page.click("#btn-fabricantes"); self.page.click('#marcas button:has-text("Fiat")')
            self.page.wait_for_selector("#lista-marca .carro")
            with self.subTest(width=w):
                self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), w + 1)
                for sel in ("#btn-fabricantes", "#btn-buscar", ".logo img", "#lista-marca .carro"):
                    box = self.page.locator(sel).first.bounding_box()
                    self.assertIsNotNone(box); self.assertLessEqual(box["x"] + box["width"], w + 1)
                self.go("/veiculo?id=1"); self.page.wait_for_selector("h1.vei-titulo")
                self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), w + 1)
                self.go("/admin"); self.page.wait_for_selector("#adm-login")
                self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), w + 1)

    # ---------------- falhas simuladas ----------------
    def test_api_down_shows_error_and_recovers(self):
        self.ctx.route("**/api/meta", lambda r: r.abort())
        self.go(); self.page.click("#btn-fabricantes")
        self.page.wait_for_selector("#lista-marca .estado.erro")
        self.assertIn("Não foi possível", self.page.inner_text("#lista-marca"))
        self.ctx.unroute("**/api/meta")
        self.page.click("#lista-marca .estado.erro button")
        self.ready(); self.assertEqual(self.page.locator("#marcas button").count(), 8)

    def test_server_error_on_list_and_missing_photo(self):
        self.go(); self.ready(); self.page.click("#btn-fabricantes")
        self.ctx.route("**/api/vehicles?brand=Fiat", lambda r: r.fulfill(status=500, content_type="application/json", body='{"error":{"code":"internal_error","message":"Erro interno. Código: abc"}}'))
        self.page.click('#marcas button:has-text("Fiat")'); self.page.wait_for_selector("#lista-marca .estado.erro")
        self.assertIn("Erro interno", self.page.inner_text("#lista-marca"))
        self.ctx.unroute("**/api/vehicles?brand=Fiat")
        self.page.click('#marcas button:has-text("Fiat")')                                    # fecha
        self.ctx.route("**/uploads/**", lambda r: r.abort())                                   # fotos indisponíveis
        self.page.click('#marcas button:has-text("Fiat")'); self.page.wait_for_selector("#lista-marca .carro")
        self.assertEqual(self.page.locator("#lista-marca .carro").count(), 3)                 # cards continuam, sem foto quebrada
        self.wait_js(self.page, "[...document.querySelectorAll('#lista-marca .thumb')].every(i => i.hidden)")

    def test_video_unavailable_does_not_break_the_page(self):
        self.ctx.route("**/video-onix.mp4", lambda r: r.abort())
        self.go(); self.ready(); self.page.click("#btn-fabricantes"); self.page.click('#marcas button:has-text("Toyota")')
        self.page.wait_for_selector("#lista-marca .carro")
        self.assertEqual([e for e in self.errors if "video-onix" not in e and "Failed to load resource" not in e], [])
        self.assertTrue(self.page.is_visible(".video-faixa"))                      # a faixa do vídeo segue com a imagem de capa (poster)

    def test_search_with_api_failure(self):
        self.go(); self.ready(); self.page.click("#btn-buscar")
        self.ctx.route("**/api/vehicles?*", lambda r: r.abort())
        self.page.select_option("#sel-cor", "Cinza"); self.page.click("#form-busca button[type=submit]")
        self.page.wait_for_selector("#resultado .estado.erro"); self.assertIn("Não foi possível", self.page.inner_text("#resultado"))

    # ---------------- administrador ----------------
    def login(self):
        self.go("/admin"); self.page.wait_for_selector("#adm-login:not([hidden])")
        self.page.fill("#adm-user", ADMIN_USER); self.page.fill("#adm-pass", ADMIN_PASS); self.page.click("#form-login button[type=submit]")
        self.page.wait_for_selector("#adm-painel:not([hidden])")

    def test_admin_login_failure_and_protection(self):
        self.go("/admin"); self.page.wait_for_selector("#adm-login:not([hidden])")
        self.assertTrue(self.page.is_hidden("#adm-painel")); self.assertEqual(self.page.locator("#adm-lista .carro").count(), 0)
        self.page.fill("#adm-user", ADMIN_USER); self.page.fill("#adm-pass", "senha-errada-123"); self.page.click("#form-login button[type=submit]")
        self.wait_js(self.page, "document.getElementById('msg-login').textContent.length > 0")
        self.assertIn("incorretos", self.page.inner_text("#msg-login")); self.assertTrue(self.page.is_hidden("#adm-painel"))
        for method, path in (("post", "/api/admin/vehicles"), ("delete", "/api/admin/vehicles/1")):
            self.assertEqual(getattr(self.ctx.request, method)(self.base + path).status, 401)

    def test_admin_full_flow_and_public_visibility(self):
        self.login()
        count_before = int(self.page.inner_text("#adm-qtd"))
        self.page.select_option("#f-marca", "Chevrolet"); self.page.fill("#f-modelo", "Spin LTZ E2E"); self.page.fill("#f-ano", "2021")
        self.page.fill("#f-cor", "Prata"); self.page.select_option("#f-cambio", "Automático")
        self.page.fill("#f-desc", "Minivan · Motor 1.8 Flex · Câmbio automático de 6 marchas."); self.page.fill("#f-detalhes", "# Câmbio\nAutomático\n# Conforto\nAr-condicionado\nDireção elétrica")
        self.page.set_input_files("#f-fotos", self.photo); self.page.click("#btn-salvar")
        self.wait_js(self.page, "document.getElementById('msg-form').textContent.includes('adicionado')")
        self.assertEqual(int(self.page.inner_text("#adm-qtd")), count_before + 1)
        new = [v for v in api(self.base, "/api/vehicles")["items"] if v["model"] == "Spin LTZ E2E"][0]
        self.assertTrue(new["photo"]); self.assertEqual(new["description"], "Minivan · Motor 1.8 Flex · Câmbio automático de 6 marchas.")
        # visitante sem login vê o carro novo, com foto e detalhes
        pub = self.ctx.browser.new_context(); pub.route(re.compile(r"https://fonts\..*"), lambda r: r.fulfill(status=200, body="", content_type="text/css"))
        pp = pub.new_page(); pp.goto(self.base + "/"); self.ready(pp); pp.click("#btn-fabricantes"); pp.click('#marcas button:has-text("Chevrolet")')
        pp.wait_for_selector('#lista-marca a.carro:has-text("Spin LTZ E2E")')
        self.wait_js(pp, "[...document.querySelectorAll('#lista-marca .thumb')].every(i => i.complete && i.naturalWidth > 0)")
        pp.click('#lista-marca a.carro:has-text("Spin LTZ E2E")'); pp.wait_for_selector("h1.vei-titulo")
        self.assertIn("Direção elétrica", pp.inner_text(".vei-blocos")); pub.close()
        # editar: descrição, situação e segunda foto
        self.page.click('#adm-lista .carro:has-text("Spin LTZ E2E") button:has-text("Editar")')
        self.wait_js(self.page, "document.getElementById('h-form').textContent === 'Editar veículo'")
        self.page.fill("#f-desc", "Descrição editada no teste."); self.page.select_option("#f-disp", "0"); self.page.set_input_files("#f-fotos", self.photo2)
        self.page.click("#btn-salvar"); self.wait_js(self.page, "document.getElementById('msg-form').textContent.includes('salvas')")
        self.wait_js(self.page, "document.querySelectorAll('#fotos-atuais .adm-foto').length === 2")
        edited = api(self.base, f"/api/vehicles/{new['id']}")
        self.assertEqual(edited["description"], "Descrição editada no teste."); self.assertFalse(edited["available"]); self.assertEqual(len(edited["photos"]), 2)
        self.page.click("#fotos-atuais .adm-foto:nth-child(2) button:has-text('Tornar principal')")
        self.wait_js(self.page, "document.querySelector('#fotos-atuais .adm-foto:nth-child(1) small') !== null")
        self.assertEqual(api(self.base, f"/api/vehicles/{new['id']}")["photos"][0]["id"], edited["photos"][1]["id"])
        self.page.click("#fotos-atuais .adm-foto:nth-child(2) button:has-text('Remover')")
        self.wait_js(self.page, "document.querySelectorAll('#fotos-atuais .adm-foto').length === 1")
        # remover o veículo
        self.page.click('#adm-lista .carro:has-text("Spin LTZ E2E") button:has-text("Remover")')
        self.wait_js(self.page, "document.getElementById('msg-form').textContent.includes('removido')")
        self.assertEqual(int(self.page.inner_text("#adm-qtd")), count_before)
        self.assertEqual([v for v in api(self.base, "/api/vehicles")["items"] if v["model"] == "Spin LTZ E2E"], [])
        # sair
        self.page.click("#btn-sair"); self.page.wait_for_selector("#adm-login:not([hidden])")
        self.page.reload(); self.page.wait_for_selector("#adm-login:not([hidden])"); self.assertTrue(self.page.is_hidden("#adm-painel"))

    def test_admin_form_validation_messages(self):
        self.login()
        self.page.click("#btn-salvar"); self.assertIn("Preencha", self.page.inner_text("#msg-form"))
        big = os.path.join(self.tmp, "grande.png")
        with open(big, "wb") as fh:
            fh.write(b"0" * (6 * 1024 * 1024))
        self.page.select_option("#f-marca", "Fiat"); self.page.fill("#f-modelo", "X"); self.page.fill("#f-ano", "2020"); self.page.select_option("#f-cambio", "Manual")
        self.page.set_input_files("#f-fotos", big); self.page.click("#btn-salvar")
        self.assertIn("5 MB", self.page.inner_text("#msg-form"))
        fake = os.path.join(self.tmp, "falsa.png")
        open(fake, "wb").write(b"isto nao e uma imagem")
        self.page.set_input_files("#f-fotos", fake); self.page.click("#btn-salvar")
        self.wait_js(self.page, "document.getElementById('msg-form').textContent.includes('imagem')")
        for v in api(self.base, "/api/vehicles")["items"]:                      # o veículo foi salvo antes do erro da foto; limpar
            if v["model"] == "X":
                self.page.click('#adm-lista .carro:has-text("Fiat X") button:has-text("Remover")'); self.wait_js(self.page, "document.getElementById('msg-form').textContent.includes('removido')")

    def test_stored_xss_does_not_execute(self):
        self.login()
        payload_model, payload_desc = "<img src=x onerror=window.__xss=1>", "<script>window.__xss=2</script><svg onload=window.__xss=3>"
        self.page.select_option("#f-marca", "Honda"); self.page.fill("#f-modelo", payload_model); self.page.fill("#f-ano", "2022"); self.page.select_option("#f-cambio", "Manual")
        self.page.fill("#f-desc", payload_desc); self.page.fill("#f-detalhes", "# <b>Título</b>\n<i>item</i>"); self.page.click("#btn-salvar")
        self.wait_js(self.page, "document.getElementById('msg-form').textContent.includes('adicionado')")
        vid = [v for v in api(self.base, "/api/vehicles")["items"] if v["model"] == payload_model][0]["id"]
        self.assertIsNone(self.page.evaluate("window.__xss"))
        pub = self.ctx.browser.new_context(); pub.route(re.compile(r"https://fonts\..*"), lambda r: r.fulfill(status=200, body="", content_type="text/css"))
        pp = pub.new_page(); seen = []; pp.on("dialog", lambda d: (seen.append(d.message), d.dismiss()))
        pp.goto(self.base + "/"); self.ready(pp); pp.click("#btn-fabricantes"); pp.click('#marcas button:has-text("Honda")')
        pp.wait_for_selector("#lista-marca .carro"); self.assertIn(payload_model, pp.inner_text("#lista-marca"))
        self.assertEqual(pp.locator("#lista-marca img[src='x']").count(), 0)
        pp.goto(self.base + f"/veiculo?id={vid}"); pp.wait_for_selector("h1.vei-titulo")
        self.assertIn(payload_model, pp.inner_text("h1.vei-titulo")); self.assertIn("<b>Título</b>", pp.inner_text(".vei-blocos"))
        self.assertIsNone(pp.evaluate("window.__xss")); self.assertEqual(seen, []); pub.close()
        self.page.click(f'#adm-lista .carro:has-text("onerror") button:has-text("Remover")'); self.wait_js(self.page, "document.getElementById('msg-form').textContent.includes('removido')")

    def test_no_secrets_reach_the_browser(self):
        self.login()
        self.assertNotIn("rm_session", self.page.evaluate("document.cookie"))              # cookie HttpOnly
        cookies = {c["name"]: c for c in self.ctx.cookies()}
        self.assertTrue(cookies["rm_session"]["httpOnly"]); self.assertEqual(cookies["rm_session"]["sameSite"], "Strict")
        self.assertEqual(self.page.evaluate("JSON.stringify([Object.keys(localStorage), Object.keys(sessionStorage)])"), "[[],[]]")
        fetched = []
        for path in ["/", "/admin", "/veiculo", "/assets/js/rm.js", "/assets/js/home.js", "/assets/js/admin.js", "/assets/js/veiculo.js", "/assets/js/video.js",
                     "/assets/css/site.css", "/assets/css/admin.css", "/assets/css/veiculo.css", "/api/meta", "/api/vehicles", "/api/auth/me"]:
            with urllib.request.urlopen(self.base + path) as r:
                fetched.append(r.read().decode("utf-8", "ignore"))
        blob = "\n".join(fetched)
        for secret in (ADMIN_PASS, "e2e-" + "k" * 40, "scrypt$", "SECRET_KEY", "password_hash"):
            self.assertNotIn(secret, blob, secret)


if __name__ == "__main__":
    unittest.main()
