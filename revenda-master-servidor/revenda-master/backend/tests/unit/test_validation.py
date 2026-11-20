import unittest

from backend.app.errors import ApiError, ValidationError
from backend.app.services.vehicle_service import validate_vehicle
from backend.tests.helpers import VEHICLE


def with_(**kw):
    d = dict(VEHICLE); d.update(kw); return d


class VehicleValidationTests(unittest.TestCase):
    def test_valid_payload_is_cleaned(self):
        out = validate_vehicle(with_(model="  Onix\x00 LT  ", year="2021"))
        self.assertEqual(out["model"], "Onix LT"); self.assertEqual(out["year"], 2021)

    def test_invalid_fields_are_reported(self):
        cases = {"brand": "Lada", "model": "", "year": 1900, "transmission": "CVT", "available": "sim",
                 "description": "x" * 301, "color": "y" * 31, "year_label": "z" * 21}
        for field, value in cases.items():
            with self.subTest(field):
                with self.assertRaises(ValidationError) as ctx:
                    validate_vehicle(with_(**{field: value}))
                self.assertIn(field, ctx.exception.fields)

    def test_wrong_types(self):
        for bad in (None, [], "texto", 5):
            with self.assertRaises(ApiError):
                validate_vehicle(bad)
        with self.assertRaises(ValidationError):
            validate_vehicle(with_(year=True))
        with self.assertRaises(ValidationError):
            validate_vehicle(with_(model=123))

    def test_sections(self):
        ok = validate_vehicle(with_(sections=[{"title": "Câmbio", "items": ["Automático", " "]}]))
        self.assertEqual(ok["sections"], [{"title": "Câmbio", "items": ["Automático"]}])
        for bad in ("x", [{"items": ["a"]}], [{"title": "T", "items": "a"}], [{"title": "T", "items": ["a"] * 21}], [{"title": "T"}] * 11):
            with self.subTest(str(bad)[:30]):
                if bad == [{"title": "T"}] * 11 or bad == "x" or bad == [{"items": ["a"]}] or isinstance(bad, list):
                    with self.assertRaises(ValidationError):
                        validate_vehicle(with_(sections=bad))


if __name__ == "__main__":
    unittest.main()
