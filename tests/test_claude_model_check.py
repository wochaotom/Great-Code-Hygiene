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
    brevity_verdict,
    claude_env,
    compare_arms,
    grade_all,
    init_fingerprint,
    is_file_change,
    is_test_command,
    load_rows,
    missing_anchors,
    new_words,
    parse_judgement,
    pooled_mean,
    ran_tests,
    region_violations,
    reproduced_first,
    result_files,
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
FINAL = {"max_cost_ratio": 1.05, "min_first_turn_token_saving": 400, "min_test_runs_ratio": 0.8, "min_pooled_delta": -1.5, "min_model_delta": -4.0,
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
        self.assertTrue(summary["reproduced_first_loose"])
        self.assertFalse(summary["reproduced_first"])  # no tool output shows a test ran
        self.assertEqual(2, summary["test_runs_loose"])
        self.assertEqual(0, summary["test_runs"])
        self.assertEqual("", summary["error"])

    def test_session_summary_without_result_keeps_the_error(self) -> None:
        summary = session_summary(stream(bash("pytest")), "boom", TARGET)
        self.assertFalse(summary["completed"])
        self.assertEqual("boom", summary["error"])


class StrictSignalTests(unittest.TestCase):
    def test_ran_tests_needs_a_nonzero_summary(self) -> None:
        for output in ("Ran 4 tests in 0.002s\n\nOK", "Ran 1 test in 0.001s\n\nFAILED (failures=1)", "3 passed in 0.10s",
                       "1 failed, 2 passed in 0.2s", "# tests 3\n# pass 2", "\u2139 tests 4"):
            with self.subTest(output=output):
                self.assertTrue(ran_tests(output))
        for output in ("Ran 0 tests in 0.000s\n\nOK", "/usr/bin/python: No module named pytest", "collected 0 items",
                       "no tests ran in 0.01s", "ImportError: Start directory is not importable", "# tests 0", "",
                       "collected 5 items",
                       "ERROR: test_x (unittest.loader._FailedTest.test_x)\nRan 1 test in 0.000s\n\nFAILED (errors=1)",
                       "ERROR: Failed to import test module: test_x\nRan 1 test in 0.001s",
                       "collected 3 items / 1 error\nERROR tests/test_x.py\n!!! Interrupted: 1 error during collection !!!\n1 error in 0.1s"):
            with self.subTest(output=output):
                self.assertFalse(ran_tests(output))

    def test_strict_reproduced_first_needs_tests_to_run(self) -> None:
        empty = ("Bash", {"command": "python -m unittest"}, "Ran 0 tests in 0.000s\n\nOK")
        real = ("Bash", {"command": "python -m unittest tests/test_x.py"}, "Ran 3 tests in 0.01s\n\nFAILED (failures=1)")
        change = ("Edit", {"file_path": f"{TARGET}/app/x.py"}, "")
        self.assertTrue(reproduced_first([empty, change], TARGET))
        self.assertFalse(reproduced_first([empty, change], TARGET, strict=True))
        self.assertTrue(reproduced_first([empty, real, change], TARGET, strict=True))
        self.assertFalse(reproduced_first([change, real], TARGET, strict=True))
        self.assertEqual(1, count_test_runs([empty, real, change], strict=True))
        self.assertEqual(2, count_test_runs([empty, real, change]))

    def test_session_summary_pairs_outputs_and_reads_first_turn_tokens(self) -> None:
        events = [
            {"type": "assistant", "message": {"usage": {"input_tokens": 3, "cache_creation_input_tokens": 1000,
                                                         "cache_read_input_tokens": 20000, "output_tokens": 5},
                                               "content": [{"type": "tool_use", "id": "t1", "name": "Bash",
                                                            "input": {"command": "python -m unittest"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                      "content": [{"type": "text", "text": "Ran 2 tests in 0.1s\n\nFAILED"}]}]}},
            {"type": "assistant", "message": {"usage": {"input_tokens": 1, "cache_creation_input_tokens": 50,
                                                         "cache_read_input_tokens": 21000, "output_tokens": 9},
                                               "content": [{"type": "tool_use", "id": "t2", "name": "Edit",
                                                            "input": {"file_path": f"{TARGET}/app/x.py"}}]}},
            {"type": "result", "subtype": "success", "num_turns": 3, "total_cost_usd": 0.05, "result": "ok", "usage": {}},
        ]
        summary = session_summary("\n".join(json.dumps(event) for event in events), "", TARGET)
        self.assertTrue(summary["reproduced_first"])
        self.assertTrue(summary["reproduced_first_loose"])
        self.assertEqual(1, summary["test_runs"])
        self.assertEqual(21003, summary["first_turn_tokens"])

    def test_init_fingerprint_tracks_the_session_environment(self) -> None:
        init = {"type": "system", "subtype": "init", "model": "claude-haiku", "claude_code_version": "2.1",
                "tools": ["Bash", "Edit"], "skills": ["a", "code-hygiene:code-hygiene"], "mcp_servers": [],
                "plugins": [{"name": "code-hygiene", "path": "/tmp/x"}], "permissionMode": "acceptEdits",
                "session_id": "s1", "cwd": "/tmp/run-1"}
        moved = {**init, "plugins": [{"name": "code-hygiene", "path": "/tmp/y"}], "cwd": "/tmp/run-2", "session_id": "s2",
                 "tools": ["Edit", "Bash"]}
        self.assertEqual(init_fingerprint([init]), init_fingerprint([moved]))
        self.assertNotEqual(init_fingerprint([init]), init_fingerprint([{**init, "skills": ["a", "b", "code-hygiene:code-hygiene"]}]))
        self.assertIsNone(init_fingerprint([]))

    def test_clean_env_uses_a_fresh_config_dir_and_keeps_auth(self) -> None:
        import os
        os.environ["HYGIENE_TEST_AUTH"] = "kept"
        try:
            env = claude_env(clean=True)
            self.assertEqual("kept", env["HYGIENE_TEST_AUTH"])
            config = Path(env["CLAUDE_CONFIG_DIR"])
            self.assertTrue(config.is_dir())
            self.assertEqual([], list(config.iterdir()))
            self.assertIsNone(claude_env(clean=False))
        finally:
            os.environ.pop("HYGIENE_TEST_AUTH")
            import shutil
            shutil.rmtree(config, ignore_errors=True)


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


class GradeAllTests(unittest.TestCase):
    def test_invalid_judgement_is_requested_again_once(self) -> None:
        calls: list[str] = []

        def judge(row: dict) -> dict:
            calls.append(row["case"])
            if row["case"] == "flaky" and calls.count("flaky") == 1:
                return {"error": "total 85 exceeds triggered cap 72"}
            if row["case"] == "broken":
                return {"error": "judge reply has no JSON object"}
            return {"total": 90.0}

        grades = grade_all([{"case": "ok"}, {"case": "flaky"}, {"case": "broken"}], judge, jobs=2, retries=1)
        self.assertEqual([{"total": 90.0}, {"total": 90.0}, {"error": "judge reply has no JSON object"}], grades)
        self.assertEqual(2, calls.count("flaky"))
        self.assertEqual(2, calls.count("broken"))
        self.assertEqual(1, calls.count("ok"))


class ResultFileTests(unittest.TestCase):
    def rows(self, model: str, rounds: int) -> list[dict]:
        return [{"setup": "invoked", "model": model, "case": case, "round": round_no, "fixed": True, "protected_files_ok": True,
                 "cost_usd": 0.1} for round_no in range(1, rounds + 1)
                for case in ("hyg-006-currency-rounding", "hyg-031-sql-injection")]

    def test_repeated_rounds_get_one_file_each(self) -> None:
        rows = self.rows("sonnet", 2) + self.rows("haiku", 1)
        grades = [{"total": 90.0, "categories": {}, "deductions": []} for _ in rows]
        files = result_files(rows, grades, commit="abc", judge="opus", now="2026-10-02T00:00:00+00:00")
        self.assertEqual({"pass100-invoked-haiku.json", "pass100-invoked-sonnet-r1.json", "pass100-invoked-sonnet-r2.json"},
                         {name for name, _ in files.values()})
        for name, payload in files.values():
            ids = [score["prompt_id"] for score in payload["scores"]]
            self.assertEqual(len(ids), len(set(ids)), name)


class BrevityTests(unittest.TestCase):
    SKILL = (FRONT + "## Workflow\nCopy this checklist into your reply:\n```\nHygiene progress:\n- [ ] Ground\n```\n"
             "### 1. Ground\nRead the code.\n### 6. Report\nFor implementation work, report the feedback loop, "
             "commands run and their results, unrun checks, assumptions, and residual risk.\n## Hard Stops\nDo not train.\n")
    REGIONS = [["### 6. Report", "## Hard Stops"], ["## Workflow", "``` Hygiene progress:"]]
    ANCHORS = {"region": ["### 6. Report", "## Hard Stops"], "RA1": [["feedback loop"]],
               "RA2": [["command", "check"], ["result"]], "RA3": [["unrun", "not run"]]}

    def test_edits_inside_regions_are_allowed(self) -> None:
        shorter = self.SKILL.replace("Copy this checklist into your reply:", "Use this checklist:").replace(
            "For implementation work, report the feedback loop, commands run and their results, unrun checks, assumptions, and residual risk.",
            "Report the feedback loop, commands and results, and unrun checks.")
        self.assertEqual([], region_violations(shorter, self.SKILL, self.REGIONS))

    def test_edits_outside_regions_are_rejected(self) -> None:
        changed = self.SKILL.replace("Read the code.", "Read code.")
        self.assertTrue(any("outside" in failure for failure in region_violations(changed, self.SKILL, self.REGIONS)))
        broken = self.SKILL.replace("## Hard Stops", "## Stops")
        self.assertTrue(any("marker" in failure for failure in region_violations(broken, self.SKILL, self.REGIONS)))

    def test_report_anchors(self) -> None:
        self.assertEqual([], missing_anchors(self.SKILL, self.ANCHORS))
        self.assertEqual(["RA2"], missing_anchors(self.SKILL.replace("and their results", ""), self.ANCHORS))
        moved = self.SKILL.replace("unrun checks, ", "").replace("Read the code.", "Read the code; note unrun checks.")
        self.assertEqual(["RA3"], missing_anchors(moved, self.ANCHORS))

    def rows(self, totals: list[float], docproc: float = 8.0, resolved: int = 12, first: int = 6) -> list[dict]:
        return [{"total": total, "categories": {"documentation": docproc / 2, "agent_process": docproc / 2},
                 "fixed": index < resolved, "protected_files_ok": True, "reproduced_first": index < first,
                 "completed": True, "error": ""} for index, total in enumerate(totals)]

    def test_brevity_verdict(self) -> None:
        guard = {"min_score_delta": -4.0, "max_capped_increase": 1, "min_doc_process_delta": -1.0, "max_unresolved": 1,
                 "min_reproduced_first": 4}
        base = self.rows([88.0] * 11 + [72.0])
        self.assertEqual("pass", brevity_verdict(self.rows([86.0] * 10 + [72.0, 72.0]), base, guard)[0])
        cases = {"score": self.rows([82.0] * 12), "capped": self.rows([95.0] * 9 + [72.0] * 3),
                 "documentation": self.rows([88.0] * 12, docproc=6.5), "unresolved": self.rows([88.0] * 12, resolved=10),
                 "reproduced": self.rows([88.0] * 12, first=3)}
        for reason, candidate in cases.items():
            with self.subTest(reason=reason):
                verdict, reasons = brevity_verdict(candidate, base, guard)
                self.assertEqual("fail", verdict)
                self.assertTrue(any(reason in text for text in reasons), reasons)
        broken = self.rows([88.0] * 12)
        broken[0] = {**broken[0], "completed": False, "error": "timed out"}
        self.assertEqual("infrastructure", brevity_verdict(broken, base, guard)[0])

    def test_pooled_mean_weighs_models_equally(self) -> None:
        rows = [{"model": "haiku", "final_report_chars": 1000}] * 6 + [{"model": "sonnet", "final_report_chars": 2000}] * 2
        self.assertEqual(1500, pooled_mean(rows, "final_report_chars"))

    def test_load_rows_carries_grade_categories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / "results.json").write_text(json.dumps([{"check": "fixtures", "setup": "invoked", "model": "haiku",
                                                            "case": "hyg-006", "round": 1}]), encoding="utf-8")
            (run / "grades.json").write_text(json.dumps([{"setup": "invoked", "model": "haiku", "case": "hyg-006", "round": 1,
                                                           "total": 80.0, "categories": {"documentation": 4},
                                                           "rubric_flags": {"x": False}}]), encoding="utf-8")
            row = load_rows(run)[0]
        self.assertEqual((80.0, {"documentation": 4}, {"x": False}), (row["total"], row["categories"], row["rubric_flags"]))


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
    def arm(self, offset: float, cost: float, first: bool = True, tokens: int = 30000, sonnet_offset: float | None = None,
            rounds: dict | None = None) -> list[dict]:
        rows = []
        for model in ("haiku", "sonnet", "opus"):
            for round_no in range(1, (rounds or {}).get(model, 1) + 1):
                for index in range(10):
                    shift = sonnet_offset if model == "sonnet" and sonnet_offset is not None else offset
                    rows.append({"model": model, "case": f"hyg-{index:03d}", "round": round_no, "total": 90 + (index % 3) + shift,
                                 "fixed": True, "protected_files_ok": True, "reproduced_first": first, "cost_usd": cost,
                                 "test_runs": 3, "usage": {"input": 1, "cache_write": 100, "cache_read": 1000, "output": 50},
                                 "turns": 8, "final_report_chars": 900, "first_turn_tokens": tokens})
        return rows

    def test_neutral_cheaper_candidate_meets_criteria(self) -> None:
        result = compare_arms(self.arm(0, 0.10), self.arm(-0.5, 0.09, tokens=29500), FINAL, holdout=["hyg-001", "hyg-002"])
        self.assertEqual(30, result["pairs"])
        self.assertAlmostEqual(-0.5, result["pooled_delta"])
        self.assertAlmostEqual(0.9, result["cost_ratio"])
        self.assertEqual({"haiku": 500, "opus": 500, "sonnet": 500}, result["first_turn_token_saving"])
        self.assertTrue(all(result["criteria"].values()), result["criteria"])

    def test_small_token_saving_fails_ac2(self) -> None:
        result = compare_arms(self.arm(0, 0.10), self.arm(0, 0.10, tokens=29700), FINAL, holdout=["hyg-001"])
        self.assertFalse(result["criteria"]["AC2"])

    def test_models_weigh_equally_when_sonnet_has_more_rounds(self) -> None:
        rounds = {"sonnet": 2}
        result = compare_arms(self.arm(0, 0.10, rounds=rounds), self.arm(0, 0.10, tokens=29500, sonnet_offset=-3, rounds=rounds),
                              FINAL, holdout=["hyg-001"])
        self.assertEqual(40, result["pairs"])
        self.assertAlmostEqual(-1.0, result["pooled_delta"])
        self.assertAlmostEqual(-3.0, result["per_model_delta"]["sonnet"])
        self.assertAlmostEqual(-1.0, result["bootstrap_interval"][0])

    def test_regressions_fail_their_criteria(self) -> None:
        worse = self.arm(-5, 0.12, first=False, tokens=29500)
        result = compare_arms(self.arm(0, 0.10), worse, FINAL, holdout=["hyg-001"])
        for criterion in ("AC2", "AC3", "AC4", "AC6"):
            self.assertFalse(result["criteria"][criterion], criterion)
        self.assertTrue(result["criteria"]["AC5"])

    def test_brevity_criteria(self) -> None:
        final = {**FINAL, "max_report_ratio": 0.7, "max_model_report_ratio": 0.85, "min_doc_process_delta": -0.5,
                 "max_capped_increase": 2}
        original, shorter = self.arm(0, 0.10), self.arm(0, 0.10, tokens=29500)
        for row in original:
            row.update(final_report_chars=1500, categories={"documentation": 4.0, "agent_process": 4.0})
        for row in shorter:
            row.update(final_report_chars=900, categories={"documentation": 4.0, "agent_process": 3.8})
        result = compare_arms(original, shorter, final, holdout=["hyg-001"])
        self.assertAlmostEqual(0.6, result["report_ratio"])
        self.assertAlmostEqual(-0.2, result["doc_process_delta"])
        self.assertTrue(result["criteria"]["report_length"] and result["criteria"]["doc_process"] and result["criteria"]["caps"])
        for row in shorter:
            if row["model"] == "opus":
                row["final_report_chars"] = 1400
            row["categories"] = {"documentation": 3.0, "agent_process": 3.0}
        for row in shorter[:3]:
            row["total"] = 70.0
        result = compare_arms(original, shorter, final, holdout=["hyg-001"])
        self.assertFalse(result["criteria"]["report_length"])
        self.assertFalse(result["criteria"]["doc_process"])
        self.assertFalse(result["criteria"]["caps"])

    def test_unpaired_rows_are_reported(self) -> None:
        original = self.arm(0, 0.1)
        result = compare_arms(original, self.arm(0, 0.09)[:-1], FINAL, holdout=[])
        self.assertEqual(29, result["pairs"])
        self.assertEqual([("opus", "hyg-009", 1)], result["unpaired"])


if __name__ == "__main__":
    unittest.main()
