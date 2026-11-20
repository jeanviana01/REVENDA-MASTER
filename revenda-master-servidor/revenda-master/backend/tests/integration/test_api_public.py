import json
import shutil
import unittest

from backend.tests.helpers import VEHICLE, hdr, login, make_app, png_bytes
import io


class PublicApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app()
        cls.client = cls.app.test_client()
        cls.token = login(cls.client)[1]
        cls.ids = []
        for brand, model, year, color, trans in [("Chevrolet", "Onix LT", 2020, "Azul", "Manual"), ("Chevrolet", "Tracker LT", 2023, "Vermelho", "Automático"),
                                                 ("Fiat", "Argo Drive", 2020, "Preto", "Manual"), ("Honda", "Civic EXL", 2022, "Branco", "Automático")]:
            body = dict(VEHICLE, brand=brand, model=model, year=year, color=color, transmission=trans)
            r = cls.client.post("/api/admin/vehicles", json=body, headers=hdr(cls.token))
            assert r.status_code == 201, r.get_json()
            cls.ids.append(r.get_json()["id"])
        cls.client.post(f"/api/admin/vehicles/{cls.ids[0]}/photos", data={"photo": (io.BytesIO(png_bytes()), "carro.png")},
                        headers=hdr(cls.token), content_type="multipart/form-data")
        cls.public = cls.app.test_client()                     # visitante, sem login

    def get(self, url):
        return self.public.get(url)

    def test_health_and_meta(self):
        self.assertEqual(self.get("/api/health").get_json(), {"status": "ok"})
        meta = self.get("/api/meta").get_json()
        self.assertIn("Volkswagen", meta["brands"]); self.assertEqual(meta["transmissions"], ["Manual", "Automático"])
        self.assertIn("Onix LT", meta["models_by_brand"]["Chevrolet"]); self.assertEqual(meta["years"], sorted(meta["years"], reverse=True))
        self.assertEqual(meta["whatsapp"], "5511999999999")

    def test_list_all_and_filters(self):
        self.assertEqual(self.get("/api/vehicles").get_json()["count"], 4)
        cases = [("brand=Chevrolet", 2), ("brand=Fiat", 1), ("year=2020", 2), ("color=Branco", 1), ("transmission=Manual", 2),
                 ("brand=Chevrolet&transmission=Manual", 1), ("model=Civic%20EXL", 1), ("brand=Honda&year=2020", 0), ("q=tracker", 1)]
        for qs, expected in cases:
            with self.subTest(qs):
                self.assertEqual(self.get("/api/vehicles?" + qs).get_json()["count"], expected)

    def test_list_item_shape_and_photo(self):
        items = {i["model"]: i for i in self.get("/api/vehicles?brand=Chevrolet").get_json()["items"]}
        self.assertTrue(items["Onix LT"]["photo"].startswith("/uploads/")); self.assertIsNone(items["Tracker LT"]["photo"])
        self.assertTrue(items["Onix LT"]["available"])
        resp = self.get(items["Onix LT"]["photo"])
        self.assertEqual(resp.status_code, 200); resp.close()

    def test_detail_and_404(self):
        d = self.get(f"/api/vehicles/{self.ids[0]}").get_json()
        self.assertEqual(d["model"], "Onix LT"); self.assertEqual(len(d["photos"]), 1); self.assertTrue(d["photos"][0]["main"])
        self.assertEqual(self.get("/api/vehicles/999999").status_code, 404)
        self.assertEqual(self.get("/api/vehicles/abc").status_code, 404)

    def test_invalid_filters(self):
        self.assertEqual(self.get("/api/vehicles?year=abc").status_code, 400)
        self.assertEqual(self.get("/api/vehicles?year=20200").status_code, 400)
        self.assertEqual(self.get("/api/vehicles?brand=" + "a" * 81).status_code, 400)
        self.assertEqual(self.get("/api/vehicles?q=" + "a" * 81).status_code, 400)

    def test_sql_injection_payloads_are_treated_as_data(self):
        payloads = ["' OR '1'='1", "'; DROP TABLE vehicles; --", "\" OR 1=1 --", "x' UNION SELECT 1,username,password_hash FROM users --", "%' OR '%'='"]
        for p in payloads:
            for key in ("brand", "model", "color", "transmission", "q"):
                with self.subTest(key=key, payload=p[:20]):
                    r = self.get("/api/vehicles", ) if False else self.public.get("/api/vehicles", query_string={key: p})
                    self.assertEqual(r.status_code, 200)
                    self.assertEqual(r.get_json()["count"], 0)
        self.assertEqual(self.get("/api/vehicles").get_json()["count"], 4)       # tabela intacta
        self.assertNotIn("password_hash", self.get("/api/vehicles").get_data(as_text=True))

    def test_like_wildcards_in_search_are_escaped(self):
        self.assertEqual(self.public.get("/api/vehicles", query_string={"q": "%"}).get_json()["count"], 0)
        self.assertEqual(self.public.get("/api/vehicles", query_string={"q": "_"}).get_json()["count"], 0)

    def test_public_cannot_use_admin(self):
        self.assertEqual(self.public.post("/api/admin/vehicles", json=VEHICLE).status_code, 401)


if __name__ == "__main__":
    unittest.main()
