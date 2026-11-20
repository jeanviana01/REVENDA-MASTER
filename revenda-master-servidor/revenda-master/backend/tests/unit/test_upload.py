import io
import unittest

from PIL import Image

from backend.app.errors import ApiError
from backend.app.services.upload_service import FILENAME_RE, process_image, save_image
from backend.tests.helpers import png_bytes
import tempfile


class UploadTests(unittest.TestCase):
    def test_png_with_alpha_stays_png(self):
        data, ext = process_image(png_bytes())
        self.assertEqual(ext, "png")
        self.assertEqual(Image.open(io.BytesIO(data)).mode, "RGBA")

    def test_jpeg_is_reencoded_without_exif(self):
        src = io.BytesIO()
        img = Image.new("RGB", (60, 40), (10, 120, 10))
        exif = Image.Exif(); exif[0x010F] = "CameraSecreta"
        img.save(src, format="JPEG", exif=exif)
        data, ext = process_image(src.getvalue())
        self.assertEqual(ext, "jpg")
        self.assertNotIn(b"CameraSecreta", data)

    def test_webp_is_accepted(self):
        buf = io.BytesIO(); Image.new("RGB", (30, 30), (1, 2, 3)).save(buf, format="WEBP")
        self.assertEqual(process_image(buf.getvalue())[1], "jpg")

    def test_large_image_is_resized(self):
        data, _ = process_image(png_bytes(size=(3000, 1000)))
        self.assertLessEqual(max(Image.open(io.BytesIO(data)).size), 1600)

    def test_rejects_non_images_and_disguised_files(self):
        cases = {"texto": b"isto nao e uma imagem", "html": b"<html><script>alert(1)</script></html>",
                 "svg": b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
                 "vazio": b"", "png_truncado": png_bytes()[:30], "php": b"<?php system($_GET['c']); ?>"}
        for nome, data in cases.items():
            with self.subTest(nome):
                with self.assertRaises(ApiError) as ctx:
                    process_image(data)
                self.assertIn(ctx.exception.status, (400, 415))

    def test_rejects_gif(self):
        buf = io.BytesIO(); Image.new("P", (10, 10)).save(buf, format="GIF")
        with self.assertRaises(ApiError) as ctx:
            process_image(buf.getvalue())
        self.assertEqual(ctx.exception.status, 415)

    def test_rejects_decompression_bomb(self):
        with self.assertRaises(ApiError) as ctx:
            process_image(png_bytes(size=(6500, 6500), mode="RGB", color=(0, 0, 0, 255)))   # ~42 mi de pixels
        self.assertIn(ctx.exception.status, (413, 415))

    def test_saved_name_is_random_and_safe(self):
        with tempfile.TemporaryDirectory() as d:
            n1, n2 = save_image(d, png_bytes()), save_image(d, png_bytes())
        self.assertNotEqual(n1, n2)
        self.assertRegex(n1, FILENAME_RE)


if __name__ == "__main__":
    unittest.main()
