import sqlite3
import unittest

from app.users import usernames_by_role


class UserQueryTests(unittest.TestCase):
    def make_conn(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE users (username TEXT, role TEXT)")
        conn.executemany(
            "INSERT INTO users (username, role) VALUES (?, ?)",
            [("alice", "user"), ("root", "admin")],
        )
        self.addCleanup(conn.close)
        return conn

    def test_returns_matching_role(self):
        self.assertEqual(usernames_by_role(self.make_conn(), "user"), ["alice"])

    def test_injected_role_does_not_return_admins(self):
        payload = "user' OR role = 'admin"
        self.assertEqual(usernames_by_role(self.make_conn(), payload), [])


if __name__ == "__main__":
    unittest.main()
