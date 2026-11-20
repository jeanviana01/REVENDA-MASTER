import unittest

from backend.scripts import audit_static


class StaticAuditTests(unittest.TestCase):
    def test_no_findings_in_source_tree(self):
        findings, _ = audit_static.audit()
        self.assertEqual(findings, [], "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
