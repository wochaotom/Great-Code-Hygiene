import json
import unittest

from app.logging_helpers import failure_log


class FailureLogTests(unittest.TestCase):
    def test_keeps_useful_structured_context(self):
        record = failure_log(
            RuntimeError("upstream timeout"),
            {"request_id": "req-123", "operation": "sync", "api_token": "secret-token"},
        )
        self.assertEqual(record["request_id"], "req-123")
        self.assertEqual(record["operation"], "sync")
        self.assertEqual(record["level"], "error")

    def test_redacts_secrets_from_log_payload(self):
        record = failure_log(
            RuntimeError("upstream timeout"),
            {"request_id": "req-123", "api_token": "secret-token"},
        )
        self.assertNotIn("secret-token", json.dumps(record, sort_keys=True))
        self.assertNotIn("api_token", record)

    def test_redacts_secret_key_variants(self):
        record = failure_log(
            RuntimeError("upstream timeout"),
            {
                "request_id": "req-123",
                "api_token_v2": "secret-token",
                "service_api_key": "secret-key",
            },
        )
        self.assertNotIn("secret-token", json.dumps(record, sort_keys=True))
        self.assertNotIn("secret-key", json.dumps(record, sort_keys=True))
        self.assertNotIn("api_token_v2", record)
        self.assertNotIn("service_api_key", record)
        self.assertEqual(record["request_id"], "req-123")

    def test_redacts_exact_secret_key_names(self):
        record = failure_log(
            RuntimeError("upstream timeout"),
            {
                "request_id": "req-123",
                "secret": "secret-value",
                "password": "password-value",
                "credential": "credential-value",
                "token": "token-value",
                "authorization": "Bearer sensitive-token",
                "Authorization": "Bearer capital-sensitive-token",
            },
        )
        serialized = json.dumps(record, sort_keys=True)
        self.assertNotIn("secret-value", serialized)
        self.assertNotIn("password-value", serialized)
        self.assertNotIn("credential-value", serialized)
        self.assertNotIn("token-value", serialized)
        self.assertNotIn("Bearer sensitive-token", serialized)
        self.assertNotIn("Bearer capital-sensitive-token", serialized)
        self.assertEqual(record["request_id"], "req-123")

    def test_preserves_non_secret_context_that_contains_key_letters(self):
        record = failure_log(
            RuntimeError("upstream timeout"),
            {"request_id": "req-123", "monkey": "banana"},
        )
        self.assertEqual(record["request_id"], "req-123")
        self.assertEqual(record["monkey"], "banana")


if __name__ == "__main__":
    unittest.main()
