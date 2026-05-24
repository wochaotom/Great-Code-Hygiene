import unittest

from app.source_audit_plan import active_activation_values
from app.source_audit_plan import validate_domains


class SourceAuditDomainTests(unittest.TestCase):
    def test_http_domain_activates_http_protocol_pack(self):
        self.assertEqual(validate_domains(["http"]), [])
        self.assertIn("http_protocol", active_activation_values(["http"]))

    def test_header_and_cookie_aliases_are_ordinary_http_language(self):
        self.assertEqual(validate_domains(["headers", "cookies"]), [])
        self.assertIn("http_protocol", active_activation_values(["headers"]))
        self.assertIn("http_protocol", active_activation_values(["cookies"]))

    def test_unknown_domain_still_fails_closed(self):
        errors = validate_domains(["typo-http"])
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown domain: typo-http", errors[0])

    def test_existing_api_domain_is_unchanged(self):
        self.assertEqual(
            active_activation_values(["api"]),
            {"always", "rest_api", "web_or_api_security"},
        )


if __name__ == "__main__":
    unittest.main()
