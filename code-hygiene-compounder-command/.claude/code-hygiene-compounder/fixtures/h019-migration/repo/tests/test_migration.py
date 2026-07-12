import unittest

from app.migration import forward


class MigrationTests(unittest.TestCase):
    def test_forward_adds_missing_column(self):
        schema = {"columns": ["id"]}

        result = forward(schema, "email")

        self.assertIs(result, schema)
        self.assertEqual(["id", "email"], schema["columns"])


if __name__ == "__main__":
    unittest.main()
