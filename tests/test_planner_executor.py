import json
import tempfile
import unittest
from pathlib import Path

from flowguard.executor import SafetyError, execute_plan, latest_journal, rollback
from flowguard.models import MoveAction
from flowguard.planner import build_organization_plan
from flowguard.scanner import scan_folder

TEST_TMP = Path(__file__).resolve().parents[1] / "work" / "test-tmp"
TEST_TMP.mkdir(parents=True, exist_ok=True)


class PlannerExecutorTests(unittest.TestCase):
    def test_dry_run_does_not_change_files(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            for name in ("one.pdf", "two.pdf", "three.pdf"):
                (root / name).write_text(name)
            actions = build_organization_plan(scan_folder(root))
            record = execute_plan(root, actions, dry_run=True)
            self.assertEqual(3, len(actions))
            self.assertTrue(all((root / name).exists() for name in ("one.pdf", "two.pdf", "three.pdf")))
            self.assertTrue(record["dry_run"])
            self.assertIsNone(latest_journal(root))

    def test_execute_collision_journal_and_rollback(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            for name in ("one.pdf", "two.pdf", "three.pdf"):
                (root / name).write_text(name)
            target = root / "FlowGuard Organized" / "Documents"
            target.mkdir(parents=True)
            (target / "one.pdf").write_text("existing")
            actions = build_organization_plan(scan_folder(root))
            execute_plan(root, actions, dry_run=False)
            self.assertTrue((target / "one (1).pdf").exists())
            journal = latest_journal(root)
            self.assertIsNotNone(journal)
            outcome = rollback(journal)
            self.assertEqual(3, len(outcome["restored"]))
            self.assertTrue((root / "one.pdf").exists())
            self.assertEqual("existing", (target / "one.pdf").read_text())

    def test_blocks_path_escape(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder, tempfile.TemporaryDirectory(dir=TEST_TMP) as outside:
            root = Path(folder)
            src = root / "safe.txt"
            src.write_text("safe")
            action = MoveAction(str(src), str(Path(outside) / "unsafe.txt"), "bad")
            with self.assertRaises(SafetyError):
                execute_plan(root, [action], dry_run=True)

    def test_journal_is_valid_json(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            src = root / "a.txt"; src.write_text("a")
            action = MoveAction(str(src), str(root / "dest" / "a.txt"), "test")
            execute_plan(root, [action], dry_run=False)
            data = json.loads(latest_journal(root).read_text(encoding="utf-8"))  # type: ignore[union-attr]
            self.assertEqual("moved", data["operations"][0]["status"])
