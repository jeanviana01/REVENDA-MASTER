import unittest

from backend.tests.helpers import ADMIN_PASS, ADMIN_USER, hdr, login, make_app


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app(login_max_attempts=3)
        self.c = self.app.test_client()

    def test_login_success_sets_hardened_cookie(self):
        r, token = login(self.c)
        self.assertEqual(r.status_code, 200); self.assertTrue(token)
        cookie = r.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie); self.assertIn("SameSite=Strict", cookie); self.assertIn("rm_session=", cookie)
        self.assertNotIn(ADMIN_PASS, r.get_data(as_text=True))
        me = self.c.get("/api/auth/me").get_json()
        self.assertTrue(me["authenticated"]); self.assertEqual(me["username"], ADMIN_USER)

    def test_wrong_credentials_same_message_for_unknown_user_and_wrong_password(self):
        a = self.c.post("/api/auth/login", json={"username": ADMIN_USER, "password": "errada12345"})
        b = self.c.post("/api/auth/login", json={"username": "ninguem", "password": "errada12345"})
        self.assertEqual((a.status_code, b.status_code), (401, 401))
        self.assertEqual(a.get_json(), b.get_json())
        self.assertFalse(self.c.get("/api/auth/me").get_json()["authenticated"])

    def test_invalid_login_bodies(self):
        self.assertEqual(self.c.post("/api/auth/login", data="username=a&password=b").status_code, 415)
        self.assertEqual(self.c.post("/api/auth/login", data="{quebrado", content_type="application/json").status_code, 400)
        for body in ({}, {"username": "a"}, {"username": 1, "password": 2}, {"username": "", "password": "x"}, {"username": "a" * 65, "password": "x"}, [1, 2]):
            with self.subTest(body=str(body)[:30]):
                self.assertEqual(self.c.post("/api/auth/login", json=body).status_code, 400)

    def test_brute_force_is_rate_limited(self):
        for _ in range(3):
            self.assertEqual(self.c.post("/api/auth/login", json={"username": ADMIN_USER, "password": "errada12345"}).status_code, 401)
        r = self.c.post("/api/auth/login", json={"username": ADMIN_USER, "password": "errada12345"})
        self.assertEqual(r.status_code, 429); self.assertIn("Retry-After", r.headers)
        self.assertEqual(self.c.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}).status_code, 429)   # nem a certa passa

    def test_logout_requires_csrf_and_kills_session(self):
        _, token = login(self.c)
        self.assertEqual(self.c.post("/api/auth/logout").status_code, 403)
        self.assertTrue(self.c.get("/api/auth/me").get_json()["authenticated"])
        old_cookie = self.c.get_cookie("rm_session").value
        self.assertEqual(self.c.post("/api/auth/logout", headers=hdr(token)).status_code, 200)
        self.assertFalse(self.c.get("/api/auth/me").get_json()["authenticated"])
        self.c.set_cookie("rm_session", old_cookie)                       # reaproveitar o cookie antigo
        self.assertFalse(self.c.get("/api/auth/me").get_json()["authenticated"])
        self.assertEqual(self.c.post("/api/admin/vehicles", json={}, headers=hdr(token)).status_code, 401)

    def test_change_password_flow(self):
        _, token = login(self.c)
        url = "/api/auth/password"
        self.assertEqual(self.c.post(url, json={"current": ADMIN_PASS, "new": "NovaSenha2026y"}).status_code, 403)          # sem CSRF
        self.assertEqual(self.c.post(url, json={"current": "errada", "new": "NovaSenha2026y"}, headers=hdr(token)).status_code, 403)
        self.assertEqual(self.c.post(url, json={"current": ADMIN_PASS, "new": "curta1"}, headers=hdr(token)).status_code, 422)
        self.assertEqual(self.c.post(url, json={"current": ADMIN_PASS, "new": 123}, headers=hdr(token)).status_code, 400)
        old_cookie = self.c.get_cookie("rm_session").value
        r = self.c.post(url, json={"current": ADMIN_PASS, "new": "NovaSenha2026y"}, headers=hdr(token))
        self.assertEqual(r.status_code, 200); self.assertNotEqual(r.get_json()["csrf_token"], token)
        self.assertTrue(self.c.get("/api/auth/me").get_json()["authenticated"])           # sessão nova segue válida
        other = self.app.test_client(); other.set_cookie("rm_session", old_cookie)
        self.assertFalse(other.get("/api/auth/me").get_json()["authenticated"])           # sessão antiga caiu
        self.assertEqual(self.app.test_client().post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}).status_code, 401)
        self.assertEqual(self.app.test_client().post("/api/auth/login", json={"username": ADMIN_USER, "password": "NovaSenha2026y"}).status_code, 200)

    def test_tampered_cookie_is_rejected(self):
        login(self.c)
        value = self.c.get_cookie("rm_session").value
        forged = self.app.test_client(); forged.set_cookie("rm_session", value[:-3] + ("AAA" if not value.endswith("AAA") else "BBB"))
        self.assertFalse(forged.get("/api/auth/me").get_json()["authenticated"])


if __name__ == "__main__":
    unittest.main()
