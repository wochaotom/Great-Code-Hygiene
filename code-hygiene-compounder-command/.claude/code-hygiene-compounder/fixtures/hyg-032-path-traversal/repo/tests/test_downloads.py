import shutil
import unittest
import uuid
from pathlib import Path

from app.downloads import resolve_download_path


class DownloadPathTests(unittest.TestCase):
    def make_root(self):
        root = Path.cwd() / f".test-root-{uuid.uuid4().hex}"
        root.mkdir()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def test_valid_relative_path_stays_inside_root(self):
        root = self.make_root()
        expected = root / "reports" / "summary.txt"
        expected.parent.mkdir()
        expected.write_text("ok", encoding="utf-8")

        self.assertEqual(resolve_download_path(root, "reports/summary.txt"), expected.resolve())

    def test_parent_traversal_is_rejected(self):
        root = self.make_root()
        with self.assertRaises(ValueError):
            resolve_download_path(root, "../secret.txt")

    def test_encoded_parent_traversal_is_rejected(self):
        root = self.make_root()
        with self.assertRaises(ValueError):
            resolve_download_path(root, "%2e%2e/secret.txt")

    def test_sibling_prefix_traversal_is_rejected(self):
        root = self.make_root()
        with self.assertRaises(ValueError):
            resolve_download_path(root, "../downloads_evil/secret.txt")
        with self.assertRaises(ValueError):
            resolve_download_path(root, "..%2fdownloads_evil%2fsecret.txt")

    def test_double_encoded_parent_traversal_is_rejected(self):
        root = self.make_root()
        with self.assertRaises(ValueError):
            resolve_download_path(root, "%252e%252e/secret.txt")
        with self.assertRaises(ValueError):
            resolve_download_path(root, "%252e%252e%252fsecret.txt")


if __name__ == "__main__":
    unittest.main()
