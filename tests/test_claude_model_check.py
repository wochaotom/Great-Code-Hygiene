from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from claude_model_check import (  # noqa: E402
    Ledger,
    behavior_verdict,
    compare_arms,
    is_file_change,
    is_test_command,
    new_words,
    parse_judgement,
    reproduced_first,
    scrub,
    session_summary,
    skill_size,
    stage_plugins,
    static_guard,
    count_test_runs,
    tree_diff,
)

FULL_MARKS = {"correctness": 15, "tests": 15, "maintainability": 15, "security": 10, "local_integration": 10,
              "minimal_diff": 10, "observability": 10, "documentation": 5, "dependencies": 5, "agent_process": 5}
TARGET = "/out/targets/run-abc"
FRONT = "---\nname: demo\ndescription: Demo skill.\n---\n"
GUARD = {"scope": ["code-hygiene/SKILL.md"], "min_step_bytes": 32, "max_new_words": 2, "reproduced_first_pass_at": 6,
         "reproduced_first_fail_at": 4, "second_stage_pass_total": 12, "max_unresolved_per_stage": 1}
FINAL = {"max_cost_ratio": 0.95, "min_test_runs_ratio": 0.8, "min_pooled_delta": -1.5, "min_model_delta": -4.0,
         "min_bootstrap_lower": -4.5, "bootstrap_confidence": 0.9, "bootstrap_seed": 7, "bootstrap_resamples": 500,
         "min_holdout_delta": -3.0, "resolved_slack": 1, "reproduced_first_slack": 3, "sonnet_reproduced_first_slack": 2}


def reply(categories: dict, flags: dict | None = None, deductions: list[str] | None = None) -> str:
    return "Here is the grade:\n" + json.dumps({"categories": categories, "rubric_flags": flags or {}, "deductions": deductions or []})


def bash(command: str) -> tuple[str, dict]:
    return ("Bash", {"command": command})


def edit(path: str) -> tuple[str, dict]:
    return ("Edit", {"file_path": path})


def stream(*calls: tuple[str, dict], result: dict | None = None) -> str:
    events = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": tool_input}]}}
              for name, tool_input in calls]
    if result is not None:
        events.append({"type": "result", **result})
    return "\n".join(json.dumps(event) for event in events) + "\n"


def guard_row(resolved: bool = True, first: bool = True) -> dict:
    return {"fixed": resolved, "protected_files_ok": True, "reproduced_first": first, "completed": True, "error": ""}


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


class SessionSignalTests(unittest.TestCase):
    def test_test_commands(self) -> None:
        for command in ("pytest -q", "python -m pytest tests", "python3 -B -m unittest discover -s tests", "npm test",
                        "node --test", "FOO=1 pytest", f"cd {TARGET} && python -m unittest -v 2>&1 | tail -20"):
            with self.subTest(command=command):
                self.assertTrue(is_test_command(command))
        for command in ("grep -rn pytest tests", "cat tests/test_app.py", "echo pytest", "pip install pytest"):
            with self.subTest(command=command):
                self.assertFalse(is_test_command(command))

    def test_file_changes(self) -> None:
        for command in ("sed -i 's/a/b/' app/x.py", "echo x > app/x.py", "cat > app/x.py <<'EOF'\nx = 1\nEOF",
                        "python - <<'E'\np='app/x.py'\ns=open(p).read()\nopen(p,'w').write(s)\nE",
                        "python3 -c \"from pathlib import Path; Path('app/x.py').write_text('x')\"",
                        "node -e \"require('fs').writeFileSync('app/x.js', '')\"",
                        "cp app/a.py app/b.py", "printf x | tee app/x.py", f"echo x >> {TARGET}/app/x.py"):
            with self.subTest(command=command):
                self.assertTrue(is_file_change("Bash", {"command": command}, TARGET))
        for command in ("python -m pytest 2>&1 | tail -5", "ls > /dev/null", "python -c 'print(1 > 0)'",
                        "echo x > /tmp/scratch.txt", "git diff"):
            with self.subTest(command=command):
                self.assertFalse(is_file_change("Bash", {"command": command}, TARGET))
        self.assertTrue(is_file_change("Edit", {"file_path": f"{TARGET}/app/x.py"}, TARGET))
        self.assertTrue(is_file_change("Write", {"file_path": "app/x.py"}, TARGET))
        self.assertFalse(is_file_change("Write", {"file_path": "/tmp/notes.md"}, TARGET))
        self.assertFalse(is_file_change("Read", {"file_path": f"{TARGET}/app/x.py"}, TARGET))

    def test_reproduced_first(self) -> None:
        cases = {
            "test before edit": ([bash("python -m pytest"), edit(f"{TARGET}/app/x.py")], True),
            "edit before test": ([edit(f"{TARGET}/app/x.py"), bash("python -m pytest")], False),
            "test inside a cd chain": ([bash(f"cd {TARGET} && python -m unittest"), edit(f"{TARGET}/app/x.py")], True),
            "grep is not a test": ([bash("grep -rn pytest ."), edit(f"{TARGET}/app/x.py"), bash("pytest")], False),
            "shell edit before test": ([bash("sed -i 's/a/b/' app/x.py"), bash("pytest")], False),
            "scratch write outside target": ([("Write", {"file_path": "/tmp/plan.md"}), bash("pytest")], True),
            "never tested": ([bash("ls"), edit(f"{TARGET}/app/x.py")], False),
            "test and write in one call is blind": ([bash("python -m pytest 2>&1 | tail -5\nsed -i 's/a/b/' app/x.py")], False),
            "script write before test": ([bash("python - <<'E'\nopen('app/x.py','w').write('x')\nE"), bash("pytest")], False),
        }
        for name, (calls, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(expected, reproduced_first(calls, TARGET))

    def test_test_runs_counts_segments(self) -> None:
        calls = [bash("pytest -q && npm test"), edit("app/x.py"), bash("grep pytest x"), bash("python -m unittest")]
        self.assertEqual(3, count_test_runs(calls))

    def test_session_summary_captures_usage_and_signals(self) -> None:
        usage = {"input_tokens": 12, "cache_creation_input_tokens": 1400, "cache_read_input_tokens": 21000, "output_tokens": 900}
        log = stream(("Skill", {"skill": "code-hygiene:code-hygiene"}), bash("pytest"), edit(f"{TARGET}/app/x.py"), bash("pytest"),
                     result={"subtype": "success", "num_turns": 5, "total_cost_usd": 0.12, "result": "Done.", "usage": usage})
        summary = session_summary(log, "", TARGET)
        self.assertEqual(["code-hygiene:code-hygiene"], summary["skills"])
        self.assertTrue(summary["completed"])
        self.assertEqual({"input": 12, "cache_write": 1400, "cache_read": 21000, "output": 900}, summary["usage"])
        self.assertEqual(5, summary["final_report_chars"])
        self.assertTrue(summary["reproduced_first"])
        self.assertEqual(2, summary["test_runs"])
        self.assertEqual("", summary["error"])

    def test_session_summary_without_result_keeps_the_error(self) -> None:
        summary = session_summary(stream(bash("pytest")), "boom", TARGET)
        self.assertFalse(summary["completed"])
        self.assertEqual("boom", summary["error"])


class SkillTextTests(unittest.TestCase):
    BODY = "# Demo\n\nBuild the smallest loop before fixing.\nThen   verify.\n"

    def test_size_ignores_frontmatter_and_whitespace(self) -> None:
        size = skill_size(FRONT + self.BODY)
        self.assertEqual(len(b"# Demo Build the smallest loop before fixing. Then verify."), size)
        self.assertEqual(size, skill_size(FRONT.replace("Demo skill.", "A much longer description.") + self.BODY))
        self.assertEqual(size, skill_size((FRONT + self.BODY).replace("\n", "\r\n")))
        self.assertEqual(size, skill_size(FRONT + self.BODY.replace("smallest loop", "smallest\n   loop")))
        self.assertLess(skill_size(FRONT + self.BODY.replace(" smallest", "")), size)

    def test_new_words(self) -> None:
        self.assertEqual(["currency", "repro"], new_words("Repro the bug; check currency rounding.", "Check the bug rounding."))
        self.assertEqual([], new_words("check bug", "Check the bug.", "unused"))


class GuardTests(unittest.TestCase):
    RULES = {"LB1": ["Build the smallest loop before fixing."]}
    BASE = FRONT + "Build the smallest loop before fixing. " + "Filler sentence that repeats the loop again. " * 3

    def guard(self, candidate: str, previous: str | None = None, changed: tuple[str, ...] = ("code-hygiene/SKILL.md",)) -> list[str]:
        return static_guard(candidate=candidate, base=self.BASE, previous=previous or self.BASE, original=self.BASE,
                            changed_files=list(changed), guard=GUARD, rules=self.RULES,
                            frontmatter=__import__("hashlib").sha256(FRONT.encode()).hexdigest())

    def test_unchanged_base_passes(self) -> None:
        self.assertEqual([], self.guard(self.BASE, changed=()))

    def test_good_step_passes(self) -> None:
        self.assertEqual([], self.guard(FRONT + "Build the smallest loop before fixing. Filler sentence that repeats the loop again."))

    def test_static_failures(self) -> None:
        cases = {
            "frontmatter": self.BASE.replace("Demo skill.", "Demo skill!"),
            "scope": None,
            "step": self.BASE.replace("again. ", "again ", 1),
            "LB1": self.BASE.replace("Build the smallest loop before fixing.", "Build a loop."),
            "new words": FRONT + "Build the smallest loop before fixing. Currency rounding hint matters.",
        }
        for reason, candidate in cases.items():
            with self.subTest(reason=reason):
                if reason == "scope":
                    failures = self.guard(self.BASE, changed=("code-hygiene/SKILL.md", "tests/test_x.py"))
                else:
                    failures = self.guard(candidate)
                self.assertTrue(any(reason in failure for failure in failures), failures)

    def test_behavior_verdict(self) -> None:
        def rows(first: int, unresolved: int = 0) -> list[dict]:
            return [guard_row(resolved=index >= unresolved, first=index < first) for index in range(12)]
        self.assertEqual("pass", behavior_verdict(rows(6), None, GUARD))
        self.assertEqual("fail", behavior_verdict(rows(4), None, GUARD))
        self.assertEqual("fail", behavior_verdict(rows(9, unresolved=2), None, GUARD))
        self.assertEqual("second-stage", behavior_verdict(rows(5), None, GUARD))
        self.assertEqual("pass", behavior_verdict(rows(5), rows(7, unresolved=1), GUARD))
        self.assertEqual("fail", behavior_verdict(rows(5), rows(6, unresolved=2), GUARD))
        self.assertEqual("fail", behavior_verdict(rows(5), rows(6), GUARD))
        broken = rows(8)
        broken[0] = {**broken[0], "completed": False, "error": "timed out"}
        self.assertEqual("infrastructure", behavior_verdict(broken, None, GUARD))


class LedgerTests(unittest.TestCase):
    def test_totals_and_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ledger = Ledger(Path(temp) / "ledger.jsonl", cap_usd=1.0)
            ledger.add("guard", 0.4)
            ledger.add("judge", 0.35)
            self.assertAlmostEqual(0.75, Ledger(Path(temp) / "ledger.jsonl", cap_usd=1.0).spent())
            ledger.check(0.2)
            with self.assertRaises(SystemExit) as raised:
                ledger.check(0.3)
            self.assertEqual(3, raised.exception.code)


class StagingTests(unittest.TestCase):
    def test_skill_file_replaces_the_staged_clean_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = Path(temp) / "SKILL.md"
            skill.write_text(FRONT + "Original text.\n", encoding="utf-8")
            plugins = stage_plugins(skill)
            try:
                self.assertEqual(skill.read_text(encoding="utf-8"), (plugins["clean"] / "SKILL.md").read_text(encoding="utf-8"))
            finally:
                import shutil
                shutil.rmtree(plugins["clean"].parent)


class CompareTests(unittest.TestCase):
    def arm(self, offset: float, cost: float, first: bool = True) -> list[dict]:
        rows = []
        for model in ("haiku", "sonnet", "opus"):
            for index in range(10):
                rows.append({"model": model, "case": f"hyg-{index:03d}", "round": 1, "total": 90 + (index % 3) + offset,
                             "fixed": True, "protected_files_ok": True, "reproduced_first": first, "cost_usd": cost,
                             "test_runs": 3, "usage": {"input": 1, "cache_write": 100, "cache_read": 1000, "output": 50},
                             "turns": 8, "final_report_chars": 900})
        return rows

    def test_neutral_cheaper_candidate_meets_criteria(self) -> None:
        result = compare_arms(self.arm(0, 0.10), self.arm(-0.5, 0.09), FINAL, holdout=["hyg-001", "hyg-002"])
        self.assertEqual(30, result["pairs"])
        self.assertAlmostEqual(-0.5, result["pooled_delta"])
        self.assertAlmostEqual(0.9, result["cost_ratio"])
        self.assertTrue(all(result["criteria"].values()), result["criteria"])

    def test_regressions_fail_their_criteria(self) -> None:
        worse = self.arm(-5, 0.10, first=False)
        result = compare_arms(self.arm(0, 0.10), worse, FINAL, holdout=["hyg-001"])
        for criterion in ("AC2", "AC3", "AC4", "AC6"):
            self.assertFalse(result["criteria"][criterion], criterion)
        self.assertTrue(result["criteria"]["AC5"])

    def test_unpaired_rows_are_reported(self) -> None:
        original = self.arm(0, 0.1)
        result = compare_arms(original, self.arm(0, 0.09)[:-1], FINAL, holdout=[])
        self.assertEqual(29, result["pairs"])
        self.assertEqual([("opus", "hyg-009", 1)], result["unpaired"])


if __name__ == "__main__":
    unittest.main()
