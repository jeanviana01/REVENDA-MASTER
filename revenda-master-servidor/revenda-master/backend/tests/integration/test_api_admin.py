import io
import os
import unittest

from backend.tests.helpers import VEHICLE, hdr, login, make_app, png_bytes


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.settings = self.app.config["SETTINGS"]
        self.c = self.app.test_client()
        self.token = login(self.c)[1]
        self.h = hdr(self.token)

    def upload(self, vid, data=None, name="foto.png", headers=None, client=None):
        return (client or self.c).post(f"/api/admin/vehicles/{vid}/photos", data={"photo": (io.BytesIO(data if data is not None else png_bytes()), name)},
                                        headers=headers if headers is not None else self.h, content_type="multipart/form-data")

    def create(self, **kw):
        r = self.c.post("/api/admin/vehicles", json=dict(VEHICLE, **kw), headers=self.h)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()

    def files(self):
        return sorted(os.listdir(self.settings.upload_dir)) if os.path.isdir(self.settings.upload_dir) else []

    # ---- acesso ----
    def test_every_admin_route_requires_login(self):
        anon = self.app.test_client()
        routes = [("post", "/api/admin/vehicles"), ("put", "/api/admin/vehicles/1"), ("delete", "/api/admin/vehicles/1"),
                  ("post", "/api/admin/vehicles/1/photos"), ("delete", "/api/admin/photos/1"), ("post", "/api/admin/photos/1/main"),
                  ("post", "/api/auth/logout"), ("post", "/api/auth/password")]
        for method, url in routes:
            with self.subTest(url=url, method=method):
                self.assertEqual(getattr(anon, method)(url, headers=self.h).status_code, 401)   # mesmo com um token CSRF "roubado"

    def test_every_write_requires_csrf_token(self):
        v = self.create()
        for method, url, kw in [("post", "/api/admin/vehicles", {"json": VEHICLE}), ("put", f"/api/admin/vehicles/{v['id']}", {"json": VEHICLE}),
                                ("delete", f"/api/admin/vehicles/{v['id']}", {}), ("post", "/api/admin/photos/1/main", {}), ("delete", "/api/admin/photos/1", {})]:
            for headers in ({}, {"X-CSRF-Token": "token-errado"}):
                with self.subTest(url=url, method=method, headers=str(headers)):
                    self.assertEqual(getattr(self.c, method)(url, headers=headers, **kw).status_code, 403)
        self.assertEqual(self.upload(v["id"], headers={}).status_code, 403)
        self.assertEqual(self.c.get(f"/api/vehicles/{v['id']}").status_code, 200)              # nada foi apagado

    def test_foreign_origin_is_blocked(self):
        r = self.c.post("/api/admin/vehicles", json=VEHICLE, headers=dict(self.h, Origin="https://evil.example"))
        self.assertEqual(r.status_code, 403); self.assertEqual(r.get_json()["error"]["code"], "origin_not_allowed")
        ok = self.c.post("/api/admin/vehicles", json=VEHICLE, headers=dict(self.h, Origin="http://localhost"))
        self.assertEqual(ok.status_code, 201)

    # ---- veículos ----
    def test_crud(self):
        v = self.create(model="Spin LTZ", sections=[{"title": "Câmbio", "items": ["Automático"]}])
        self.assertEqual(v["sections"][0]["title"], "Câmbio")
        r = self.c.put(f"/api/admin/vehicles/{v['id']}", json=dict(VEHICLE, model="Spin Premier", description="Nova descrição", available=False), headers=self.h)
        self.assertEqual(r.status_code, 200); self.assertEqual(r.get_json()["model"], "Spin Premier"); self.assertFalse(r.get_json()["available"])
        self.assertEqual(self.c.get(f"/api/vehicles/{v['id']}").get_json()["description"], "Nova descrição")
        self.assertEqual(self.c.delete(f"/api/admin/vehicles/{v['id']}", headers=self.h).status_code, 204)
        self.assertEqual(self.c.get(f"/api/vehicles/{v['id']}").status_code, 404)
        self.assertEqual(self.c.delete(f"/api/admin/vehicles/{v['id']}", headers=self.h).status_code, 404)
        self.assertEqual(self.c.put("/api/admin/vehicles/9999", json=VEHICLE, headers=self.h).status_code, 404)

    def test_validation_errors(self):
        for body, field in [({"brand": "Lada"}, "brand"), ({"model": ""}, "model"), ({"year": 1800}, "year"), ({"transmission": "CVT"}, "transmission")]:
            r = self.c.post("/api/admin/vehicles", json=dict(VEHICLE, **body), headers=self.h)
            with self.subTest(field):
                self.assertEqual(r.status_code, 422); self.assertIn(field, r.get_json()["error"]["fields"])
        self.assertEqual(self.c.post("/api/admin/vehicles", data="x", headers=self.h).status_code, 415)
        self.assertEqual(self.c.post("/api/admin/vehicles", data="{ruim", content_type="application/json", headers=self.h).status_code, 400)
        self.assertEqual(self.c.post("/api/admin/vehicles", json=[1], headers=self.h).status_code, 400)
        self.assertEqual(self.c.get("/api/vehicles").get_json()["count"], 0)

    def test_extra_fields_cannot_overwrite_internal_columns(self):
        v = self.create(id=999, created_at="1999-01-01", photo="/uploads/x.png", **{"extra": "x"})
        self.assertNotEqual(v["id"], 999)

    def test_stored_xss_text_is_kept_as_plain_text(self):
        v = self.create(model='<img src=x onerror=alert(1)>', description="<script>alert(1)</script>")
        data = self.app.test_client().get(f"/api/vehicles/{v['id']}")
        self.assertEqual(data.mimetype, "application/json"); self.assertIn("nosniff", data.headers["X-Content-Type-Options"])
        self.assertEqual(data.get_json()["model"], '<img src=x onerror=alert(1)>')

    # ---- fotos ----
    def test_photo_lifecycle_and_files_on_disk(self):
        v = self.create()
        d1 = self.upload(v["id"]).get_json(); self.assertEqual(len(d1["photos"]), 1)
        d2 = self.upload(v["id"], png_bytes(color=(0, 0, 255, 255))).get_json(); self.assertEqual(len(d2["photos"]), 2)
        self.assertEqual(len(self.files()), 2)
        first, second = d2["photos"]
        self.assertTrue(first["main"]); self.assertFalse(second["main"])
        d3 = self.c.post(f"/api/admin/photos/{second['id']}/main", headers=self.h).get_json()
        self.assertEqual(d3["photos"][0]["id"], second["id"]); self.assertEqual(self.c.get("/api/vehicles").get_json()["items"][0]["photo"], second["url"])
        d4 = self.c.delete(f"/api/admin/photos/{second['id']}", headers=self.h).get_json()
        self.assertEqual(len(d4["photos"]), 1); self.assertEqual(len(self.files()), 1)
        self.assertEqual(self.c.delete(f"/api/admin/photos/{second['id']}", headers=self.h).status_code, 404)
        self.assertEqual(self.c.delete(f"/api/admin/vehicles/{v['id']}", headers=self.h).status_code, 204)
        self.assertEqual(self.files(), [])                                     # remover o veículo apaga as fotos do disco

    def test_malicious_and_invalid_uploads_are_rejected(self):
        v = self.create()
        cases = {"php_disfarçado": (b"<?php system('id'); ?>", "shell.png"), "html": (b"<script>alert(1)</script>", "x.html"),
                 "svg": (b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>", "x.svg"), "texto_com_ext_png": (b"nao sou imagem", "a.png"),
                 "caminho": (png_bytes(), "../../etc/passwd.png")}
        for name, (data, filename) in cases.items():
            with self.subTest(name):
                r = self.upload(v["id"], data=data, name=filename)
                if name == "caminho":                       # imagem válida: aceita, mas o nome enviado é ignorado
                    self.assertEqual(r.status_code, 201)
                    self.assertTrue(all(len(f) == 36 and f.endswith((".png", ".jpg")) for f in self.files()))
                else:
                    self.assertIn(r.status_code, (400, 415))
        self.assertEqual(self.c.post(f"/api/admin/vehicles/{v['id']}/photos", headers=self.h, data={}, content_type="multipart/form-data").status_code, 400)
        self.assertEqual(self.upload(9999).status_code, 404)

    def test_oversized_upload_is_rejected(self):
        app = make_app(max_upload_mb=1)
        c = app.test_client(); h = hdr(login(c)[1])
        v = c.post("/api/admin/vehicles", json=VEHICLE, headers=h).get_json()
        r = c.post(f"/api/admin/vehicles/{v['id']}/photos", data={"photo": (io.BytesIO(b"0" * (3 * 1024 * 1024)), "g.png")}, headers=h, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 413)

    def test_photo_limit_per_vehicle(self):
        app = make_app(max_photos_per_vehicle=2)
        c = app.test_client(); h = hdr(login(c)[1])
        v = c.post("/api/admin/vehicles", json=VEHICLE, headers=h).get_json()
        codes = [self.upload(v["id"], client=c, headers=h).status_code for _ in range(3)]
        self.assertEqual(codes, [201, 201, 409])

    def test_write_rate_limit(self):
        codes = {self.c.post("/api/admin/vehicles", json={}, headers=self.h).status_code for _ in range(125)}
        self.assertIn(429, codes)


if __name__ == "__main__":
    unittest.main()
