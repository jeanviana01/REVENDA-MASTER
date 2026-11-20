import unittest

from backend.app.security import (RateLimiter, csrf_matches, hash_password, origin_allowed, password_problem, verify_password)


class PasswordTests(unittest.TestCase):
    def test_hash_is_salted_and_verifiable(self):
        a, b = hash_password("SenhaForte2026x"), hash_password("SenhaForte2026x")
        self.assertNotEqual(a, b)                                    # sal diferente a cada hash
        self.assertTrue(a.startswith("scrypt$"))
        self.assertNotIn("SenhaForte2026x", a)                       # nunca em texto puro
        self.assertTrue(verify_password("SenhaForte2026x", a))
        self.assertFalse(verify_password("senhaforte2026x", a))

    def test_malformed_hash_is_rejected_without_exception(self):
        for bad in ("", "abc", "scrypt$1$2$3$x$y", "md5$1$2$3$4$5"):
            self.assertFalse(verify_password("x", bad))

    def test_password_rules(self):
        self.assertIsNotNone(password_problem("curta1"))
        self.assertIsNotNone(password_problem("somenteletrasmesmo"))
        self.assertIsNotNone(password_problem("12345678901"))
        self.assertIsNotNone(password_problem("Admin12345", "admin12345"))
        self.assertIsNone(password_problem("SenhaForte2026x", "admin"))


class RateLimiterTests(unittest.TestCase):
    def test_blocks_after_limit_and_releases_after_window(self):
        now = [0.0]
        rl = RateLimiter(clock=lambda: now[0])
        for _ in range(3):
            self.assertEqual(rl.hit("k", 3, 60)[0], True)
        ok, retry = rl.hit("k", 3, 60)
        self.assertFalse(ok); self.assertGreaterEqual(retry, 1)
        now[0] = 61
        self.assertTrue(rl.hit("k", 3, 60)[0])

    def test_keys_are_independent_and_reset_works(self):
        rl = RateLimiter()
        rl.record("a", 60); rl.record("a", 60)
        self.assertTrue(rl.blocked("a", 2, 60)[0])
        self.assertFalse(rl.blocked("b", 2, 60)[0])
        rl.reset("a")
        self.assertFalse(rl.blocked("a", 2, 60)[0])


class CsrfOriginTests(unittest.TestCase):
    def test_csrf(self):
        self.assertTrue(csrf_matches("abc", "abc"))
        for exp, got in (("abc", "abd"), ("abc", ""), ("", "abc"), (None, None), ("abc", None)):
            self.assertFalse(csrf_matches(exp, got))

    def test_origin(self):
        self.assertTrue(origin_allowed("https://loja.com", "loja.com", ()))
        self.assertTrue(origin_allowed("https://outro.com", "loja.com", ("https://outro.com",)))
        self.assertFalse(origin_allowed("https://evil.com", "loja.com", ()))
        self.assertFalse(origin_allowed("https://loja.com.evil.com", "loja.com", ()))


if __name__ == "__main__":
    unittest.main()
