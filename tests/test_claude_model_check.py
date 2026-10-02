from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from claude_model_check import parse_judgement, scrub, tree_diff  # noqa: E402

FULL_MARKS = {"correctness": 15, "tests": 15, "maintainability": 15, "security": 10, "local_integration": 10,
              "minimal_diff": 10, "observability": 10, "documentation": 5, "dependencies": 5, "agent_process": 5}


def reply(categories: dict, flags: dict | None = None, deductions: list[str] | None = None) -> str:
    return "Here is the grade:\n" + json.dumps({"categories": categories, "rubric_flags": flags or {}, "deductions": deductions or []})


class ClaudeModelCheckTests(unittest.TestCase):
    def test_total_is_the_category_sum(self) -> None:
        categories = {**FULL_MARKS, "tests": 12.5}
        graded = parse_judgement(reply(categories, deductions=["Did not rerun the failing test."]))
        self.assertEqual(97.5, graded["total"])

    def test_triggered_cap_must_hold(self) -> None:
        with self.assertRaisesRegex(ValueError, "cap 72"):
            parse_judgement(reply({**FULL_MARKS, "tests": 10}, {"feasible_feedback_loop_missing": True}, ["Patched from inspection."]))

    def test_score_below_full_marks_needs_a_deduction(self) -> None:
        with self.assertRaisesRegex(ValueError, "without deductions"):
            parse_judgement(reply({**FULL_MARKS, "documentation": 4}))

    def test_scrub_hides_target_path_and_folder_name(self) -> None:
        target = "/tmp/out/targets/invoked-opus-hyg-006"
        text = f"ran pytest in {target} and also /tmp/out-mangled/invoked-opus-hyg-006/app"
        self.assertNotIn("invoked-opus", scrub(text, target))

    def test_tree_diff_skips_bytecode_caches(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            before, after = Path(temp) / "before", Path(temp) / "after"
            for tree in (before, after):
                (tree / "app").mkdir(parents=True)
                (tree / "app" / "pricing.py").write_text("x = 1\n", encoding="utf-8")
            (after / "app" / "pricing.py").write_text("x = 2\n", encoding="utf-8")
            (after / "app" / "__pycache__").mkdir()
            (after / "app" / "__pycache__" / "pricing.cpython-311.pyc").write_bytes(b"\0")
            diff = tree_diff(before, after)
        self.assertIn("+x = 2", diff)
        self.assertNotIn("__pycache__", diff)


if __name__ == "__main__":
    unittest.main()
