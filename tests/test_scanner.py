import os
import tempfile
import time
import unittest
from pathlib import Path

from flowguard.scanner import scan_folder

TEST_TMP = Path(__file__).resolve().parents[1] / "work" / "test-tmp"
TEST_TMP.mkdir(parents=True, exist_ok=True)


class ScannerTests(unittest.TestCase):
    def test_detects_extensions_duplicate_names_and_stale(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            for name in ("a.pdf", "b.pdf", "c.pdf"):
                (root / name).write_text(name)
            (root / "sub").mkdir()
            (root / "sub" / "a.pdf").write_text("other")
            old = root / "old.txt"
            old.write_text("old")
            timestamp = time.time() - 200 * 86400
            os.utime(old, (timestamp, timestamp))
            kinds = {item.kind for item in scan_folder(root).patterns}
            self.assertEqual({"extensions", "duplicate_names", "stale"}, kinds)

    def test_rejects_non_folder(self):
        with self.assertRaises(ValueError):
            scan_folder("this-folder-should-not-exist")
