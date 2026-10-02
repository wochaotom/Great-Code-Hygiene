#!/usr/bin/env python3
"""Run the hygiene skills through Claude Code on several models and tabulate the results.

  fixtures  Run executable fixtures through `claude -p` and score each target with
            fixture_runner. Setups: `none` (no hygiene plugins), `available` (both
            plugins loaded, request does not name a skill), `invoked` (request starts
            with /code-hygiene:code-hygiene).
  triggers  Send everyday requests that never name the skill and record whether the
            model loads code-hygiene on its own. Setups: `description` (plugins only)
            and `claude-md` (plus a one-line project CLAUDE.md instruction).
  grade     Score a finished `fixtures` run against PASS-100 with a blind judge model,
            write model-execution result files, and compare each setup with `none`
            using validate_results.py and analyze_runs.py.
  size      Print the normalized body size of a SKILL.md (bytes after the frontmatter,
            whitespace runs collapsed).
  metrics   Recompute reproduced-first, test runs, and token usage from the logs of a
            finished `fixtures` run.
  guard     Check a candidate code-hygiene/SKILL.md against a token-diet spec: static
            checks first, then explicit-skill sessions on the spec's train fixtures.
            Exit 0 pass, 1 behavioral fail, 2 static fail, 3 budget, 4 infrastructure.
  compare   Pair two graded `fixtures` runs (original and candidate skill) and evaluate
            the spec's acceptance criteria.
  measure   Run the spec's measure sessions on a SKILL.md text, grade them with the blind
            judge, cache the run by the text's hash, and print the pooled final-report
            length (the loop metric for report brevity).

Plugins load with --plugin-dir from a temporary copy of this checkout, so nothing is
installed and a model exploring the skill's folder cannot reach the fixture repos.
--skill-file swaps the staged code-hygiene SKILL.md for another text, such as the
original skill in a before/after comparison. --ledger and --budget-usd record every
session's reported cost and refuse new sessions past the cap.
Skills or plugins already enabled in your Claude Code config also compete; point
CLAUDE_CONFIG_DIR at a clean config to isolate the run. Every run calls the model
and uses your Claude usage.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import difflib
import hashlib
import json
import os
import random
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
TRAINER_ROOT = REPO_ROOT / "code-hygiene-compounder"
sys.path.insert(0, str(TRAINER_ROOT / "scripts"))

from fixture_runner import copy_fixture_repo, find_fixture, run_fixture_target  # noqa: E402
from internal.policy import CATEGORY_KEYS, RUBRIC_CAPS  # noqa: E402

CLEAN_SKILL = "code-hygiene:code-hygiene"
ALLOWED_TOOLS = "Bash Read Edit Write Glob Grep Skill"
DEFAULT_FIXTURES = ("hyg-006-currency-rounding", "hyg-083-config-precedence")
TRIGGER_REQUESTS = {
    "review": ("hyg-031-sql-injection", "Can you look over app/ and tell me if anything is wrong before I ship it?"),
    "debug": ("hyg-083-config-precedence", "Some tests are failing in this repo. Figure out why and fix it."),
    "refactor": ("hyg-006-currency-rounding", "app/pricing.py is messy. Clean it up without changing what it does."),
    "harden": ("hyg-032-path-traversal", "Is the download code in app/ safe to expose publicly? Fix anything risky."),
}
CLAUDE_MD_LINE = "For code reviews, bug fixes, refactors, and hardening in this repo, use the code-hygiene skill.\n"
DIFF_SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"}
# Keeps one judge prompt well inside the context window while showing any realistic fixture diff.
MAX_JUDGE_SECTION_CHARS = 20000
# Upper bounds for one session or judge call, from the 2026-10-02 runs (Opus fixture sessions averaged 0.21 USD).
SESSION_RESERVE_USD = 0.5
JUDGE_RESERVE_USD = 0.4
SEGMENT_BREAKS = {"&&", "||", ";", "|", "|&", "&", ";;", "(", ")"}
SHELL_WRITES = (("sed", "-i"), ("perl", "-i"), ("cp",), ("mv",), ("rm",), ("patch",), ("git", "apply"), ("git", "checkout"), ("tee",))
FILE_REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
FILE_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}
PYTHON = re.compile(r"python(3(\.\d+)?)?(\.exe)?$")
ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
WORD = re.compile(r"[a-z][a-z0-9]*")
# A test runner's summary line showing that at least one test ran (unittest, pytest, node --test).
RAN_TESTS = re.compile(r"\bRan [1-9]\d* tests?\b|\b[1-9]\d* (passed|failed)\b|^\s*[#ℹ]\s*tests [1-9]\d*", re.M)
# Output where the runner counted a test that never ran: an unimportable module or a collection error.
NO_TESTS_RAN = re.compile(r"_FailedTest|Failed to import test module|Interrupted:|error during collection")
# File writes from inline scripts (python - <<EOF, python -c, node -e), which shell parsing cannot see.
SCRIPT_WRITE = re.compile(r"(?<!stdout)(?<!stderr)\.write\(|\.write_(text|bytes)\(|(writeFileSync|appendFileSync)\(|shutil\.(copy|move)")


def claude_executable() -> str:
    executable = shutil.which("claude")
    if executable is None:
        raise SystemExit("claude CLI not found on PATH")
    return executable


def stage_plugins(skill_file: Path | None = None) -> dict[str, Path]:
    """Copy both editions to a fresh temporary folder, as an install would.

    Claude Code tells the model where a skill lives. Loading plugins straight from this checkout
    led a model to the repository, where the fixture repos and their lessons sit next to the skill.
    """
    root = Path(tempfile.mkdtemp(prefix="hygiene-plugins-"))
    ignore = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".mypy_cache", "runs")
    plugins = {"clean": root / "code-hygiene", "trainer": root / "code-hygiene-compounder"}
    shutil.copytree(REPO_ROOT / "code-hygiene", plugins["clean"], ignore=ignore)
    shutil.copytree(TRAINER_ROOT, plugins["trainer"], ignore=ignore)
    if skill_file is not None:
        shutil.copyfile(skill_file, plugins["clean"] / "SKILL.md")
    return plugins


def split_skill(text: str) -> tuple[str, str]:
    """Split a SKILL.md into its frontmatter (through the closing `---` line) and body, with LF line endings."""
    text = text.replace("\r\n", "\n")
    end = text.find("\n---\n", 3) if text.startswith("---\n") else -1
    return (text[:end + 5], text[end + 5:]) if end >= 0 else ("", text)


def normalized_body(text: str) -> str:
    return " ".join(split_skill(text)[1].split())


def skill_size(text: str) -> int:
    """UTF-8 bytes of the body with whitespace runs collapsed, so reflowing text cannot move it."""
    return len(normalized_body(text).encode("utf-8"))


def frontmatter_sha256(text: str) -> str:
    return hashlib.sha256(split_skill(text)[0].encode("utf-8")).hexdigest()


def missing_rules(text: str, rules: dict[str, list[str]]) -> list[str]:
    """Rule ids whose frozen sentences no longer appear verbatim in the normalized body."""
    body = normalized_body(text)
    return [rule for rule, sentences in rules.items() if any(" ".join(sentence.split()) not in body for sentence in sentences)]


def new_words(candidate: str, *references: str) -> list[str]:
    """Lowercase words in the candidate that no reference uses: new vocabulary, abbreviations, or hints."""
    known = {word for text in references for word in WORD.findall(text.lower())}
    return sorted(set(WORD.findall(candidate.lower())) - known)


def region_violations(candidate: str, base: str, regions: list[list[str]]) -> list[str]:
    """Failures when the candidate's normalized body changed outside the editable (start, end) marker regions."""
    def outside(text: str) -> list[str] | None:
        body, parts, position = normalized_body(text), [], 0
        spans = []
        for start, end in regions:
            begin = body.find(start)
            finish = body.find(end, begin + len(start)) if begin >= 0 else -1
            if begin < 0 or finish < 0:
                return None
            spans.append((begin, begin + len(start), finish))
        for begin, inner, finish in sorted(spans):
            parts.append(body[position:inner])
            position = finish
        parts.append(body[position:])
        return parts

    before, after = outside(base), outside(candidate)
    if after is None or before is None:
        return ["editable-region marker missing or moved"]
    for old, new in zip(before, after):
        if old != new:
            index = next((i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
            return [f"text changed outside editable regions near: {new[max(0, index - 40):index + 40]!r}"]
    return []


def missing_anchors(text: str, anchors: dict) -> list[str]:
    """Anchor ids whose phrase groups no longer all match inside the anchors' region (case-insensitive)."""
    body = normalized_body(text).lower()
    start, end = (marker.lower() for marker in anchors["region"])
    begin = body.find(start)
    finish = body.find(end, begin + len(start)) if begin >= 0 else -1
    if begin < 0 or finish < 0:
        return ["region"]
    region = body[begin:finish]
    return [key for key, groups in anchors.items() if key != "region"
            and not all(any(phrase.lower() in region for phrase in group) for group in groups)]


def shell_segments(command: str) -> list[list[str]]:
    """Split a shell command into simple-command word lists at control operators, line by line."""
    segments: list[list[str]] = []
    for line in command.splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError:  # an unbalanced quote, such as a multi-line python -c body
            tokens = line.split()
        current: list[str] = []
        for token in tokens:
            if token in SEGMENT_BREAKS:
                segments.append(current)
                current = []
            else:
                current.append(token)
        segments.append(current)
    return [segment for segment in segments if segment]


def command_words(segment: list[str]) -> list[str]:
    index = 0
    while index < len(segment) and ENV_ASSIGNMENT.match(segment[index]):
        index += 1
    return segment[index:]


def is_test_segment(segment: list[str]) -> bool:
    words = command_words(segment)
    if not words:
        return False
    if words[0] == "pytest" or words[:2] in (["npm", "test"], ["node", "--test"]):
        return True
    if PYTHON.match(Path(words[0]).name):
        for index, word in enumerate(words[1:-1], start=1):
            if word == "-m":
                return words[index + 1] in ("pytest", "unittest")
            if not word.startswith("-"):
                return False
    return False


def inside(path: str, target: str) -> bool:
    return not path.startswith("/") or path == target or path.startswith(target.rstrip("/") + "/")


def is_write_segment(segment: list[str], target: str) -> bool:
    words = command_words(segment)
    if any(tuple(words[:len(prefix)]) == prefix for prefix in SHELL_WRITES):
        return True
    return any(word in FILE_REDIRECTS and index + 1 < len(words) and words[index + 1] != "/dev/null" and inside(words[index + 1], target)
               for index, word in enumerate(words))


def is_test_command(command: str) -> bool:
    return any(is_test_segment(segment) for segment in shell_segments(command))


def is_file_change(name: str, tool_input: dict, target: str) -> bool:
    if name in FILE_TOOLS:
        return inside(str(tool_input.get("file_path") or tool_input.get("notebook_path") or ""), target)
    if name == "Bash":
        command = str(tool_input.get("command", ""))
        return bool(SCRIPT_WRITE.search(command)) or any(is_write_segment(segment, target) for segment in shell_segments(command))
    return False


def ran_tests(output: str) -> bool:
    """True when a test runner's output shows that at least one test ran."""
    return bool(RAN_TESTS.search(output)) and not NO_TESTS_RAN.search(output)


def is_test_call(call: tuple, strict: bool) -> bool:
    name, tool_input = call[0], call[1]
    if name != "Bash" or not is_test_command(str(tool_input.get("command", ""))):
        return False
    return not strict or ran_tests(call[2] if len(call) > 2 else "")


def reproduced_first(calls: list[tuple], target: str, strict: bool = False) -> bool:
    """True when a call that ran a test came before the first call that changed a file inside the target.

    A test and a write in the same call do not count: the agent changed code before it saw the result.
    Calls are (name, input) or (name, input, output); strict also requires the output to show a test ran.
    """
    for call in calls:
        if is_file_change(call[0], call[1], target):
            return False
        if is_test_call(call, strict):
            return True
    return False


def count_test_runs(calls: list[tuple], strict: bool = False) -> int:
    if strict:
        return sum(is_test_call(call, strict) for call in calls)
    return sum(is_test_segment(segment) for call in calls if call[0] == "Bash"
               for segment in shell_segments(str(call[1].get("command", ""))))


def stream_events(stdout: str) -> list[dict]:
    events = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def tool_calls(events: list[dict]) -> list[tuple[str, dict]]:
    return [(str(block.get("name")), block.get("input") or {}) for event in events if event.get("type") == "assistant"
            for block in event.get("message", {}).get("content", []) if block.get("type") == "tool_use"]


def tool_outputs(events: list[dict]) -> dict[str, str]:
    """Tool output text by tool_use_id."""
    outputs = {}
    for event in events:
        content = event.get("message", {}).get("content") if event.get("type") == "user" else None
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_result":
                value = block.get("content")
                if isinstance(value, list):
                    value = "\n".join(str(part.get("text", "")) for part in value if isinstance(part, dict))
                outputs[str(block.get("tool_use_id"))] = str(value or "")
    return outputs


def tool_calls_with_output(events: list[dict]) -> list[tuple[str, dict, str]]:
    outputs = tool_outputs(events)
    return [(str(block.get("name")), block.get("input") or {}, outputs.get(str(block.get("id")), ""))
            for event in events if event.get("type") == "assistant"
            for block in event.get("message", {}).get("content", []) if block.get("type") == "tool_use"]


def init_fingerprint(events: list[dict]) -> str | None:
    """Short hash of the session environment: model, Claude Code version, tools, skills, plugins, and MCP servers."""
    init = next((event for event in events if event.get("type") == "system" and event.get("subtype") == "init"), None)
    if init is None:
        return None
    names = lambda items: sorted(str(item.get("name", item)) if isinstance(item, dict) else str(item) for item in items or [])
    environment = {"model": init.get("model"), "version": init.get("claude_code_version"), "tools": names(init.get("tools")),
                   "skills": names(init.get("skills")), "plugins": names(init.get("plugins")),
                   "mcp_servers": names(init.get("mcp_servers")), "permission_mode": init.get("permissionMode")}
    return hashlib.sha256(json.dumps(environment, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def first_turn_tokens(events: list[dict]) -> int | None:
    """Context size of the first model call: input plus cache-write plus cache-read tokens."""
    for event in events:
        usage = event.get("message", {}).get("usage") if event.get("type") == "assistant" else None
        if usage:
            return sum(int(usage.get(key) or 0) for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return None


def session_summary(stdout: str, error: str, target: str) -> dict:
    events = stream_events(stdout)
    calls = tool_calls_with_output(events)
    result = next((event for event in reversed(events) if event.get("type") == "result"), {})
    usage = result.get("usage") or {}
    final_report = result.get("result") or ""
    return {
        "skills": [str(tool_input.get("skill")) for name, tool_input, _ in calls if name == "Skill"],
        "completed": bool(result),
        "stop_reason": result.get("subtype"),
        "turns": result.get("num_turns"),
        "cost_usd": result.get("total_cost_usd"),
        "final_report": final_report,
        "final_report_chars": len(final_report),
        "usage": {"input": usage.get("input_tokens", 0), "cache_write": usage.get("cache_creation_input_tokens", 0),
                  "cache_read": usage.get("cache_read_input_tokens", 0), "output": usage.get("output_tokens", 0)},
        "reproduced_first": reproduced_first(calls, target, strict=True),
        "reproduced_first_loose": reproduced_first(calls, target),
        "test_runs": count_test_runs(calls, strict=True),
        "test_runs_loose": count_test_runs(calls),
        "first_turn_tokens": first_turn_tokens(events),
        "init_fingerprint": init_fingerprint(events),
        "error": error if not result else "",
    }


class Ledger:
    """Append-only record of reported model cost that refuses work past a cap."""

    def __init__(self, path: Path | None, cap_usd: float | None) -> None:
        self.path, self.cap_usd, self.lock = path, cap_usd, threading.Lock()

    def spent(self) -> float:
        if self.path is None or not self.path.is_file():
            return 0.0
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return sum(float(json.loads(line).get("cost_usd") or 0) for line in lines if line.strip())

    def check(self, reserve: float) -> None:
        spent = self.spent()
        if self.cap_usd is not None and spent + reserve > self.cap_usd:
            print(f"budget: spent ${spent:.2f}; another ${reserve:.2f} could pass the ${self.cap_usd:.2f} cap", file=sys.stderr)
            raise SystemExit(3)

    def add(self, label: str, cost_usd: float | None) -> None:
        if self.path is None:
            return
        entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "label": label, "cost_usd": cost_usd or 0}
        with self.lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")


def claude_command(model: str, max_turns: int, plugin_dirs: list[Path]) -> list[str]:
    command = [claude_executable(), "-p", "--model", model, "--output-format", "stream-json", "--verbose",
               "--max-turns", str(max_turns), "--permission-mode", "acceptEdits", "--allowedTools", ALLOWED_TOOLS]
    for plugin_dir in plugin_dirs:
        command += ["--plugin-dir", str(plugin_dir)]
    return command


def claude_env(clean: bool) -> dict[str, str] | None:
    """Environment for a model session; clean gives it a fresh, empty Claude Code config folder.

    Authentication in managed environments comes from environment variables, which are kept, while user
    skills, plugins, and settings in the default config folder stay out of the session.
    """
    if not clean:
        return None
    return {**os.environ, "CLAUDE_CONFIG_DIR": tempfile.mkdtemp(prefix="hygiene-config-")}


def run_claude(command: list[str], prompt: str, cwd: Path, log: Path, timeout: int, clean: bool = False) -> dict:
    """Run one session (prompt on stdin, so variadic flags cannot swallow it) and summarize it."""
    env = claude_env(clean)
    try:
        completed = subprocess.run(command, input=prompt, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        stdout, error = completed.stdout, completed.stderr.strip()
    except subprocess.TimeoutExpired as exc:
        stdout, error = exc.stdout or "", f"timed out after {timeout}s"
        stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
    finally:
        if env is not None:
            shutil.rmtree(env["CLAUDE_CONFIG_DIR"], ignore_errors=True)
    log.write_text(stdout, encoding="utf-8")
    return session_summary(stdout, error, str(cwd))


def task_prompt(item: dict) -> str:
    """The fixture title is the concrete task; name only the protected tests and the grader's file rule.

    Protected files outside tests/ (such as user notes) stay unnamed: the fixture checks whether the
    agent leaves them alone unprompted.
    """
    tests = [path for path in item.get("protected_files", []) if path.startswith("tests/")]
    protected = f"Do not change {', '.join(tests)}, and do not" if tests else "Do not"
    return f"{item['title']}. Work in this repository. {protected} add or remove files under tests/."


def fixture_job(args: argparse.Namespace, model: str, fixture_id: str, setup: str, round_no: int) -> dict:
    item = find_fixture(TRAINER_ROOT / "fixtures", fixture_id)
    prompt = task_prompt(item)
    if setup == "invoked":
        prompt = f"/{CLEAN_SKILL} {prompt}"
    # An opaque folder name keeps the setup and model out of paths the blind judge reads.
    target = args.out / "targets" / f"run-{uuid.uuid4().hex[:12]}"
    copy_fixture_repo(item, target, force=True)
    plugin_dirs = {"none": [], "invoked": [args.plugins["clean"]], "available": list(args.plugins.values())}[setup]
    session = run_claude(claude_command(model, args.max_turns, plugin_dirs), prompt, target, target.parent / f"{target.name}.jsonl",
                         args.timeout, getattr(args, "clean_config", False))
    score = run_fixture_target(item, target, args.timeout)
    return {"check": "fixtures", "setup": setup, "model": model, "case": fixture_id, "round": round_no,
            "target": str(target), "fixed": score["outcome"] == "pass", "test_outcome": score["outcome"],
            "protected_files_ok": score["protected_files_ok"], "protected_file_failures": score["protected_file_failures"],
            "loaded_skill": CLEAN_SKILL in session["skills"] or setup == "invoked", **session}


def trigger_job(args: argparse.Namespace, model: str, request: str, setup: str, round_no: int) -> dict:
    fixture_id, prompt = TRIGGER_REQUESTS[request]
    target = args.out / "targets" / f"{setup}-{model}-{request}-r{round_no}"
    copy_fixture_repo(find_fixture(TRAINER_ROOT / "fixtures", fixture_id), target, force=True)
    if setup == "claude-md":
        (target / "CLAUDE.md").write_text(CLAUDE_MD_LINE, encoding="utf-8")
    session = run_claude(claude_command(model, args.max_turns, list(args.plugins.values())), prompt, target, target.parent / f"{target.name}.jsonl",
                         args.timeout, getattr(args, "clean_config", False))
    return {"check": "triggers", "setup": setup, "model": model, "case": request, "round": round_no,
            "loaded_skill": CLEAN_SKILL in session["skills"], **session}


def summarize(rows: list[dict], models: list[str], setups: list[str], key: str) -> str:
    hits, totals = Counter(), Counter()
    for row in rows:
        for column in (row["model"], "total"):
            totals[(row["setup"], column)] += 1
            hits[(row["setup"], column)] += bool(row[key])
    columns = [*models, "total"]
    lines = [f"{key}:", "| Setup | " + " | ".join(columns) + " |", "| --- |" + " --- |" * len(columns)]
    for setup in setups:
        cells = [f"{hits[(setup, column)]}/{totals[(setup, column)]}" for column in columns]
        lines.append(f"| {setup} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def tree_diff(baseline: Path, target: Path) -> str:
    def files(root: Path) -> dict[str, Path]:
        return {path.relative_to(root).as_posix(): path for path in root.rglob("*")
                if path.is_file() and not DIFF_SKIP_PARTS & set(path.relative_to(root).parts)}
    before, after = files(baseline), files(target)
    chunks: list[str] = []
    for name in sorted(set(before) | set(after)):
        old = before[name].read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if name in before else []
        new = after[name].read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if name in after else []
        chunks.extend(difflib.unified_diff(old, new, f"a/{name}", f"b/{name}"))
    return "".join(chunks) or "(no changes)"


def scrub(text: str, target: str) -> str:
    """Hide the target path, including copies the agent retyped, from the blind judge."""
    return text.replace(target, "<repo>").replace(Path(target).name, "<repo>")


def action_log(log: Path, target: str) -> str:
    """One line per tool call, in order, so the judge can see whether checks ran before and after edits."""
    lines: list[str] = []
    for name, tool_input in tool_calls(stream_events(log.read_text(encoding="utf-8") if log.is_file() else "")):
        detail = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("pattern") or ""
        detail = " ".join(scrub(str(detail), target).split())
        lines.append(f"{len(lines) + 1}. {name}: {detail[:200]}")
    return "\n".join(lines) or "(no tool calls)"


def clip(text: str) -> str:
    return text if len(text) <= MAX_JUDGE_SECTION_CHARS else text[:MAX_JUDGE_SECTION_CHARS] + "\n[truncated]\n"


def judge_prompt(row: dict) -> str:
    item = find_fixture(TRAINER_ROOT / "fixtures", row["case"])
    rubric = (TRAINER_ROOT / "references" / "PASS-100.md").read_text(encoding="utf-8")
    rubric = "## Scoring" + rubric.split("## Scoring", 1)[1].split("## Result Schema", 1)[0]
    baseline = Path(str(item["_fixture_root"])) / str(item["repo_dir"])
    categories = ", ".join(f'"{key}": 0-{maximum}' for key, maximum in CATEGORY_KEYS.items())
    flags = ", ".join(f'"{key}": true|false' for key in RUBRIC_CAPS)
    return f"""You are grading one coding agent run against the PASS-100 rubric below. Do not use tools; answer from the material given. You do not know which agent or configuration produced this run; grade only what is shown.

{rubric}
Task given to the agent:
{task_prompt(item)}

Objective test result from the fixture harness (run after the agent finished): outcome={row['test_outcome']}, protected test files unchanged={row['protected_files_ok']}, protected file findings={json.dumps(row['protected_file_failures'])}

Agent's tool calls, in order:
{clip(action_log(Path(row['target'] + '.jsonl'), row['target']))}

Diff of the repository after the agent's work:
```diff
{clip(tree_diff(baseline, Path(row['target'])))}
```

Agent's final message:
<<<
{clip(scrub(row['final_report'] or '(none)', row['target']))}
>>>

Reply with only one JSON object of this shape:
{{"categories": {{{categories}}}, "rubric_flags": {{{flags}}}, "deductions": ["one short sentence with evidence per deduction"]}}
Use half-point steps. A true rubric flag caps the total (the sum of categories) at that cap's limit, so lower category scores until the sum is at or below the lowest triggered cap. List at least one deduction for any total below 100."""


def parse_judgement(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("judge reply has no JSON object")
    payload = json.loads(text[start:end + 1])
    categories = {key: float(payload["categories"][key]) for key in CATEGORY_KEYS}
    flags = {key: bool(payload.get("rubric_flags", {}).get(key, False)) for key in RUBRIC_CAPS}
    total = sum(categories.values())
    caps = [RUBRIC_CAPS[key] for key, flagged in flags.items() if flagged]
    if caps and total > min(caps):
        raise ValueError(f"total {total:g} exceeds triggered cap {min(caps)}")
    deductions = [str(entry) for entry in payload.get("deductions", []) if str(entry).strip()]
    if total < 100 and not deductions:
        raise ValueError("score below 100 without deductions")
    return {"categories": categories, "total": total, "rubric_flags": flags, "deductions": deductions}


def grade_job(judge: str, row: dict, timeout: int, ledger: Ledger, clean: bool = False, run: str = "") -> dict:
    ledger.check(JUDGE_RESERVE_USD)
    env = claude_env(clean)
    try:
        with tempfile.TemporaryDirectory(prefix="hygiene-judge-") as workdir:
            command = [claude_executable(), "-p", "--model", judge, "--output-format", "json", "--max-turns", "1",
                       "--disable-slash-commands"]
            completed = subprocess.run(command, input=judge_prompt(row), cwd=workdir, capture_output=True, text=True,
                                       timeout=timeout, env=env)
    finally:
        if env is not None:
            shutil.rmtree(env["CLAUDE_CONFIG_DIR"], ignore_errors=True)
    reply = json.loads(completed.stdout) if completed.stdout.strip().startswith("{") else {}
    ledger.add(f"judge {run} {row['setup']} {row['model']} {row['case']} r{row['round']}", reply.get("total_cost_usd"))
    try:
        return {**parse_judgement(reply.get("result", "")), "judge_cost_usd": reply.get("total_cost_usd")}
    except (ValueError, KeyError, TypeError) as exc:
        return {"error": f"{exc}; stderr: {completed.stderr.strip()[:200]}"}


def grade_all(rows: list[dict], judge, jobs: int, retries: int) -> list[dict]:
    """Grade every row; ask again, up to `retries` times, for a reply that breaks the rubric's rules."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        grades = list(pool.map(judge, rows))
        for _ in range(retries):
            failed = [index for index, result in enumerate(grades) if "error" in result]
            for index, result in zip(failed, pool.map(judge, [rows[index] for index in failed])):
                grades[index] = result
    return grades


def result_files(rows: list[dict], grades: list[dict], commit: str, judge: str, now: str) -> dict[tuple, tuple[str, dict]]:
    """Model-execution result payloads: one per setup and model, or per round when a run repeats fixtures."""
    rounds = Counter((row["setup"], row["model"], row["round"]) for row in rows)
    repeated = {(setup, model) for setup, model, round_no in rounds if round_no > 1}
    files: dict[tuple, tuple[str, dict]] = {}
    for key in sorted({(row["setup"], row["model"], row["round"] if (row["setup"], row["model"]) in repeated else 0) for row in rows}):
        setup, model, round_no = key
        scores = []
        for row, result in zip(rows, grades):
            if (row["setup"], row["model"]) != (setup, model) or (round_no and row["round"] != round_no):
                continue
            item = find_fixture(TRAINER_ROOT / "fixtures", row["case"])
            scores.append({"prompt_id": item["prompt_id"], "total": result["total"], "categories": result["categories"],
                           "deductions": result["deductions"], "lessons": [], "resolved": row["fixed"] and row["protected_files_ok"],
                           "cost_usd": row["cost_usd"] or 0})
        suffix = f"-r{round_no}" if round_no else ""
        payload = {"run_id": f"{setup}-{model}{suffix}", "run_type": "model-execution", "phase": 0,
                   "prompt_ids": sorted({score["prompt_id"] for score in scores}), "scores": scores,
                   "model": model, "skill_version": commit, "harness": f"claude -p; judge {judge}",
                   "started_at": now, "completed_at": now}
        files[key] = (f"pass100-{setup}-{model}{suffix}.json", payload)
    return files


def grade(args: argparse.Namespace) -> None:
    rows = json.loads((args.run / "results.json").read_text(encoding="utf-8"))
    rows = [row for row in rows if row.get("check") == "fixtures"]
    broken = [(row["model"], row["case"], row["round"]) for row in rows if not row.get("target")]
    if broken:
        print(f"not graded, session never ran: {broken}")
    rows = [row for row in rows if row.get("target")]
    if not rows:
        raise SystemExit(f"no fixtures results in {args.run}")
    if args.from_grades:
        saved = {(grade["setup"], grade["model"], grade["case"], grade["round"]): grade
                 for grade in json.loads((args.run / "grades.json").read_text(encoding="utf-8"))}
        grades = [saved[(row["setup"], row["model"], row["case"], row["round"])] for row in rows]
    else:
        ledger = Ledger(args.ledger, args.budget_usd)
        grades = grade_all(rows, lambda row: grade_job(args.judge, row, args.timeout, ledger, args.clean_config, args.run.name),
                           args.jobs, args.retries)
        failed = [(row["setup"], row["model"], row["case"], result["error"]) for row, result in zip(rows, grades) if "error" in result]
        if failed:
            raise SystemExit("judge failures:\n" + "\n".join(map(str, failed)))
        graded = [{**{key: row[key] for key in ("setup", "model", "case", "round")}, **result} for row, result in zip(rows, grades)]
        (args.run / "grades.json").write_text(json.dumps(graded, indent=2), encoding="utf-8")

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    files: dict[tuple, Path] = {}
    for key, (name, payload) in result_files(rows, grades, commit, args.judge, now).items():
        files[key] = args.run / name
        files[key].write_text(json.dumps(payload, indent=2), encoding="utf-8")

    scripts, suite = TRAINER_ROOT / "scripts", TRAINER_ROOT / "references" / "eval-prompts.md"
    for path in files.values():
        subprocess.run([sys.executable, "-B", str(scripts / "validate_results.py"), "--results", str(path), "--suite", str(suite)],
                       check=True, capture_output=True, text=True)
    print("| Setup | Model | Average | Resolved |\n| --- | --- | --- | --- |")
    for (setup, model, round_no), path in files.items():
        scores = json.loads(path.read_text(encoding="utf-8"))["scores"]
        average = sum(score["total"] for score in scores) / len(scores)
        label = f"{model} r{round_no}" if round_no else model
        print(f"| {setup} | {label} | {average:.1f} | {sum(score['resolved'] for score in scores)}/{len(scores)} |")
    for (setup, model, round_no), path in files.items():
        if setup != "none" and ("none", model, round_no) in files:
            out = args.run / f"analysis-{setup}-vs-none-{model}{f'-r{round_no}' if round_no else ''}.json"
            # analyze_runs.py exits non-zero when it detects a regression; that is a verdict, not a crash.
            completed = subprocess.run([sys.executable, "-B", str(scripts / "analyze_runs.py"), "--results", str(path),
                                        "--baseline", str(files[("none", model, round_no)]), "--suite", str(suite), "--out", str(out)],
                                       capture_output=True, text=True)
            if not out.is_file():
                raise SystemExit(f"analyze_runs.py failed for {setup} {model}: {completed.stderr.strip()[-400:]}")
            comparison = json.loads(out.read_text(encoding="utf-8"))["comparison"]
            verdict = "regression" if comparison.get("regression_detected") else "no regression"
            print(f"{setup} vs none, {model}: average delta {comparison['average_delta']:+.2f}, {verdict}. Wrote {out}")
    judge_cost = sum(result.get("judge_cost_usd") or 0 for result in grades)
    source = "from saved grades" if args.from_grades else f"with {args.judge}"
    print(f"Graded {len(rows)} sessions {source}; reported judge cost ${judge_cost:.2f}.")


def run_sessions(args: argparse.Namespace) -> None:
    args.out = args.out.resolve()
    if args.out == REPO_ROOT or REPO_ROOT in args.out.parents:
        raise SystemExit("--out must be outside the repository")
    if args.out.exists():
        raise SystemExit(f"--out already exists: {args.out}")
    if args.check == "fixtures":
        setups = args.setups or ["available", "invoked"]
        cases, job = args.fixtures or list(DEFAULT_FIXTURES), fixture_job
        allowed, args.max_turns = {"none", "available", "invoked"}, args.max_turns or 40
    else:
        setups = args.setups or ["description", "claude-md"]
        cases, job = list(TRIGGER_REQUESTS), trigger_job
        allowed, args.max_turns = {"description", "claude-md"}, args.max_turns or 8
    if not set(setups) <= allowed:
        raise SystemExit(f"--setups for {args.check} must be from: {', '.join(sorted(allowed))}")
    if args.check == "fixtures":
        for case in cases:
            find_fixture(TRAINER_ROOT / "fixtures", case)
    (args.out / "targets").mkdir(parents=True)
    args.plugins = stage_plugins(getattr(args, "skill_file", None))
    plan = [(model, case, setup, round_no) for round_no in range(1, args.rounds + 1)
            for setup in setups for model in args.models for case in cases]
    try:
        rows = run_plan(args, job, plan, Ledger(args.ledger, args.budget_usd))
    finally:
        shutil.rmtree(next(iter(args.plugins.values())).parent, ignore_errors=True)
    rows.sort(key=lambda row: (row["setup"], row["model"], row["case"], row["round"]))
    (args.out / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    keys = ("loaded_skill", "fixed", "protected_files_ok", "reproduced_first") if args.check == "fixtures" else ("loaded_skill",)
    print()
    print("\n\n".join(summarize(rows, args.models, setups, key) for key in keys))
    cost = sum(row["cost_usd"] or 0 for row in rows)
    errors = [row for row in rows if row["error"] or not row["completed"]]
    print(f"\n{len(rows)} sessions, reported cost ${cost:.2f}, {len(errors)} incomplete. Results: {args.out / 'results.json'}")
    if any(str(row["error"]).startswith("budget") for row in rows):
        raise SystemExit(3)
    if errors:
        raise SystemExit(1)


def run_plan(args: argparse.Namespace, job, plan: list[tuple], ledger: Ledger) -> list[dict]:
    """Run sessions concurrently; retry a session that broke before finishing; charge every attempt to the ledger."""
    def guarded(model: str, case: str, setup: str, round_no: int) -> dict:
        for attempt in range(args.retries + 1):
            try:
                ledger.check(SESSION_RESERVE_USD)
            except SystemExit:
                return failed_row(args.check, model, case, setup, round_no, "budget: ledger cap reached")
            try:
                row = job(args, model, case, setup, round_no)
            except (Exception, SystemExit) as exc:  # one broken session must not discard the others
                row = failed_row(args.check, model, case, setup, round_no, f"{type(exc).__name__}: {exc}")
            ledger.add(f"{args.check} {args.out.name} {setup} {model} {case} r{round_no} a{attempt + 1}", row.get("cost_usd"))
            if row["completed"] and not row["error"]:
                break
        return row

    rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(guarded, *entry) for entry in plan]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows.append(row)
            print(f"{row['setup']:<11} {row['model']:<10} {row['case']:<34} r{row['round']} loaded_skill={row['loaded_skill']}"
                  + (f" fixed={row['fixed']}" if "fixed" in row else "")
                  + (f" reproduced_first={row['reproduced_first']}" if "reproduced_first" in row else "")
                  + (f" error={row['error']}" if row["error"] else ""), flush=True)
    return rows


def failed_row(check: str, model: str, case: str, setup: str, round_no: int, error: str) -> dict:
    return {"check": check, "setup": setup, "model": model, "case": case, "round": round_no, "loaded_skill": False,
            "fixed": False, "protected_files_ok": False, "reproduced_first": False, "test_runs": 0, "completed": False,
            "cost_usd": None, "error": error}


def git(*arguments: str) -> str:
    completed = subprocess.run(["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True)
    if completed.returncode:
        raise SystemExit(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout


def static_guard(*, candidate: str, base: str, previous: str, original: str, changed_files: list[str], guard: dict,
                 rules: dict[str, list[str]], frontmatter: str, regions: list[list[str]] | None = None,
                 anchors: dict | None = None) -> list[str]:
    """Model-free checks on a candidate SKILL.md; returns the failures, cheapest first."""
    failures = []
    if frontmatter_sha256(candidate) != frontmatter:
        failures.append("frontmatter changed")
    outside = sorted(set(changed_files) - set(guard["scope"]))
    if outside:
        failures.append(f"scope: files outside scope changed: {', '.join(outside)}")
    if guard["min_step_bytes"] and normalized_body(candidate) != normalized_body(base):
        saved = skill_size(previous) - skill_size(candidate)
        if saved < guard["min_step_bytes"]:
            failures.append(f"step saved {saved} normalized bytes; need at least {guard['min_step_bytes']}")
    if regions:
        failures.extend(region_violations(candidate, base, regions))
    missing = missing_rules(candidate, rules)
    if missing:
        failures.append(f"load-bearing rules missing or reworded: {', '.join(missing)}")
    if anchors:
        lost = missing_anchors(candidate, anchors)
        if lost:
            failures.append(f"report anchors missing: {', '.join(lost)}")
    added = new_words(normalized_body(candidate), normalized_body(original), normalized_body(base))
    if len(added) > guard["max_new_words"]:
        failures.append(f"new words {len(added)} > {guard['max_new_words']}: {', '.join(added)}")
    return failures


def behavior_verdict(first: list[dict], second: list[dict] | None, guard: dict) -> str:
    """Two-stage guard on resolved sessions and the reproduced-first count (thresholds in the spec)."""
    rows = first + (second or [])
    if any(not row.get("completed") or row.get("error") for row in rows):
        return "infrastructure"

    def unresolved(stage: list[dict]) -> int:
        return sum(not (row["fixed"] and row["protected_files_ok"]) for row in stage)

    hits = sum(bool(row["reproduced_first"]) for row in first)
    if unresolved(first) > guard["max_unresolved_per_stage"]:
        return "fail"
    if second is None:
        if hits >= guard["reproduced_first_pass_at"]:
            return "pass"
        return "fail" if hits <= guard["reproduced_first_fail_at"] else "second-stage"
    if unresolved(second) > guard["max_unresolved_per_stage"]:
        return "fail"
    return "pass" if hits + sum(bool(row["reproduced_first"]) for row in second) >= guard["second_stage_pass_total"] else "fail"


def pooled_mean(rows: list[dict], field: str) -> float:
    """Mean of the per-model means, so a model with more sessions does not outweigh the others."""
    models = sorted({row["model"] for row in rows})
    return statistics.mean(statistics.mean(row[field] for row in rows if row["model"] == model) for model in models)


def doc_process(row: dict) -> float:
    categories = row.get("categories") or {}
    return float(categories.get("documentation", 0)) + float(categories.get("agent_process", 0))


def brevity_verdict(candidate: list[dict], base: list[dict], guard: dict) -> tuple[str, list[str]]:
    """Judge-based guard for a candidate's measured sessions against the base text's measured sessions."""
    if not candidate or any(not row.get("completed") or row.get("error") for row in candidate):
        return "infrastructure", ["a measured session did not finish"]

    def mean(rows: list[dict], value) -> float:
        return statistics.mean(value(row) for row in rows)

    def capped(rows: list[dict]) -> int:
        return sum(row["total"] <= 72 for row in rows)

    reasons = []
    score = mean(candidate, lambda row: row["total"]) - mean(base, lambda row: row["total"])
    if score < guard["min_score_delta"]:
        reasons.append(f"score delta {score:+.2f} below {guard['min_score_delta']}")
    if capped(candidate) > capped(base) + guard["max_capped_increase"]:
        reasons.append(f"capped sessions {capped(candidate)} vs base {capped(base)}")
    process = mean(candidate, doc_process) - mean(base, doc_process)
    if process < guard["min_doc_process_delta"]:
        reasons.append(f"documentation+process delta {process:+.2f} below {guard['min_doc_process_delta']}")
    unresolved = sum(not (row["fixed"] and row["protected_files_ok"]) for row in candidate)
    if unresolved > guard["max_unresolved"]:
        reasons.append(f"unresolved sessions {unresolved}")
    first = sum(bool(row["reproduced_first"]) for row in candidate)
    if first < guard["min_reproduced_first"]:
        reasons.append(f"reproduced first {first} below {guard['min_reproduced_first']}")
    return ("fail" if reasons else "pass"), reasons


def compare_arms(original: list[dict], candidate: list[dict], final: dict, holdout: list[str]) -> dict:
    """Pair sessions by model, case, and round and evaluate the spec's run-based acceptance criteria.

    Pooled figures are the mean of the per-model means, so a model run for more rounds does not outweigh the others.
    """
    def key(row: dict) -> tuple:
        return (row["model"], row["case"], row["round"])

    before, after = {key(row): row for row in original}, {key(row): row for row in candidate}
    pairs = sorted(set(before) & set(after))
    models = sorted({pair[0] for pair in pairs})
    by_model = {model: [pair for pair in pairs if pair[0] == model] for model in models}
    deltas = {pair: after[pair]["total"] - before[pair]["total"] for pair in pairs}

    def pooled(values: dict[str, float]) -> float:
        return statistics.mean(values.values())

    per_model = {model: statistics.mean(deltas[pair] for pair in by_model[model]) for model in models}
    held = {model: [deltas[pair] for pair in by_model[model] if pair[1] in holdout] for model in models}
    held = {model: statistics.mean(values) for model, values in held.items() if values}

    rng = random.Random(final["bootstrap_seed"])
    strata = {model: [deltas[pair] for pair in by_model[model]] for model in models}
    means = sorted(pooled({model: statistics.mean([rng.choice(stratum) for _ in stratum]) for model, stratum in strata.items()})
                   for _ in range(final["bootstrap_resamples"]))
    tail = (1 - final["bootstrap_confidence"]) / 2
    interval = (means[int(tail * len(means))], means[int((1 - tail) * len(means)) - 1])

    def model_mean(arm: dict, model: str, field: str) -> float:
        return statistics.mean(float(arm[pair].get(field) or 0) for pair in by_model[model])

    def ratio(field: str) -> float | None:
        old = pooled({model: model_mean(before, model, field) for model in models})
        new = pooled({model: model_mean(after, model, field) for model in models})
        return new / old if old else None

    def count(arm: dict, field: str, model: str | None = None) -> int:
        return sum(bool(arm[pair][field]) for pair in pairs if model is None or pair[0] == model)

    for arm in (before, after):
        for pair in pairs:
            arm[pair]["resolved"] = bool(arm[pair]["fixed"] and arm[pair]["protected_files_ok"])
    components = {}
    if all("usage" in arm[pair] for arm in (before, after) for pair in pairs):
        for field in ("input", "cache_write", "cache_read", "output"):
            old = pooled({model: statistics.mean(before[pair]["usage"][field] for pair in by_model[model]) for model in models})
            new = pooled({model: statistics.mean(after[pair]["usage"][field] for pair in by_model[model]) for model in models})
            components[field] = new / old if old else None
    token_saving = None
    if all(arm[pair].get("first_turn_tokens") is not None for arm in (before, after) for pair in pairs):
        token_saving = {model: round(model_mean(before, model, "first_turn_tokens") - model_mean(after, model, "first_turn_tokens"), 1)
                        for model in models}
    result = {
        "pairs": len(pairs),
        "pairs_per_model": {model: len(by_model[model]) for model in models},
        "unpaired": sorted(set(before) ^ set(after)),
        "pooled_delta": pooled(per_model) if per_model else None,
        "per_model_delta": per_model,
        "bootstrap_interval": interval,
        "holdout_pairs": sum(1 for pair in pairs if pair[1] in holdout),
        "holdout_delta": pooled(held) if held else None,
        "cost_ratio": ratio("cost_usd"),
        "test_runs_ratio": ratio("test_runs"),
        "turns_ratio": ratio("turns"),
        "final_report_chars_ratio": ratio("final_report_chars"),
        "token_ratios": components,
        "first_turn_token_saving": token_saving,
        "report_ratio": ratio("final_report_chars"),
        "report_ratio_per_model": {model: (model_mean(after, model, "final_report_chars") / model_mean(before, model, "final_report_chars")
                                           if model_mean(before, model, "final_report_chars") else None) for model in models},
        "resolved": {"original": count(before, "resolved"), "candidate": count(after, "resolved")},
        "reproduced_first": {"original": count(before, "reproduced_first"), "candidate": count(after, "reproduced_first"),
                             "sonnet_original": count(before, "reproduced_first", "sonnet"),
                             "sonnet_candidate": count(after, "reproduced_first", "sonnet")},
    }
    if all(arm[pair].get("categories") for arm in (before, after) for pair in pairs):
        result["doc_process_delta"] = pooled({model: statistics.mean(doc_process(after[pair]) - doc_process(before[pair])
                                                                     for pair in by_model[model]) for model in models})
    result["capped"] = {"original": sum(before[pair]["total"] <= 72 for pair in pairs),
                        "candidate": sum(after[pair]["total"] <= 72 for pair in pairs)}
    first = result["reproduced_first"]
    tokens_ok = ("min_first_turn_token_saving" not in final
                 or (token_saving is not None and min(token_saving.values()) >= final["min_first_turn_token_saving"]))
    result["criteria"] = {
        "AC2": tokens_ok and result["cost_ratio"] is not None and result["cost_ratio"] <= final["max_cost_ratio"]
               and (result["test_runs_ratio"] is None or result["test_runs_ratio"] >= final["min_test_runs_ratio"]),
        "AC3": result["pooled_delta"] >= final["min_pooled_delta"] and min(per_model.values()) >= final["min_model_delta"]
               and interval[0] >= final["min_bootstrap_lower"],
        "AC4": result["holdout_delta"] is not None and result["holdout_delta"] >= final["min_holdout_delta"],
        "AC5": result["resolved"]["candidate"] >= result["resolved"]["original"] - final["resolved_slack"],
        "AC6": first["candidate"] >= first["original"] - final["reproduced_first_slack"]
               and first["sonnet_candidate"] >= first["sonnet_original"] - final["sonnet_reproduced_first_slack"],
    }
    if "max_report_ratio" in final:
        per_model = [value for value in result["report_ratio_per_model"].values() if value is not None]
        result["criteria"]["report_length"] = (result["report_ratio"] is not None and result["report_ratio"] <= final["max_report_ratio"]
                                               and all(value <= final["max_model_report_ratio"] for value in per_model))
    if "min_doc_process_delta" in final:
        result["criteria"]["doc_process"] = ("doc_process_delta" in result
                                             and result["doc_process_delta"] >= final["min_doc_process_delta"])
    if "max_capped_increase" in final:
        result["criteria"]["caps"] = result["capped"]["candidate"] <= result["capped"]["original"] + final["max_capped_increase"]
    return result


def load_rows(run: Path) -> list[dict]:
    """Rows of a finished fixtures run, with metrics.json and grades.json merged in when present."""
    source = run / "metrics.json" if (run / "metrics.json").is_file() else run / "results.json"
    rows = [row for row in json.loads(source.read_text(encoding="utf-8")) if row.get("check") == "fixtures"]
    if (run / "grades.json").is_file():
        grades = {(grade["setup"], grade["model"], grade["case"], grade["round"]): grade
                  for grade in json.loads((run / "grades.json").read_text(encoding="utf-8"))}
        for row in rows:
            grade = grades.get((row["setup"], row["model"], row["case"], row["round"]), {})
            row.update(total=grade.get("total"), categories=grade.get("categories"), rubric_flags=grade.get("rubric_flags"))
    return rows


def metrics(args: argparse.Namespace) -> None:
    rows = [row for row in json.loads((args.run / "results.json").read_text(encoding="utf-8")) if row.get("check") == "fixtures"]
    for row in rows:
        name = Path(row["target"]).name
        log = args.run / "targets" / f"{name}.jsonl"
        log = log if log.is_file() else Path(row["target"] + ".jsonl")
        if not log.is_file():
            raise SystemExit(f"no session log for {row['setup']} {row['model']} {row['case']}: {log}")
        summary = session_summary(log.read_text(encoding="utf-8"), row.get("error") or "", row["target"])
        row.update({key: summary[key] for key in ("reproduced_first", "test_runs", "usage", "final_report_chars")})
    (args.run / "metrics.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    setups, models = sorted({row["setup"] for row in rows}), sorted({row["model"] for row in rows})
    print(summarize(rows, models, setups, "reproduced_first"))
    print("\n| Setup | Model | Test runs | Cache write | Cache read | Output | Report chars |\n| --- | --- | --- | --- | --- | --- | --- |")
    for setup in setups:
        for model in models:
            cell = [row for row in rows if (row["setup"], row["model"]) == (setup, model)]
            means = [statistics.mean(row["test_runs"] for row in cell)] + [statistics.mean(row["usage"][field] for row in cell)
                     for field in ("cache_write", "cache_read", "output")] + [statistics.mean(row["final_report_chars"] for row in cell)]
            print(f"| {setup} | {model} | " + " | ".join(f"{value:.1f}" for value in means) + " |")
    print(f"Wrote {args.run / 'metrics.json'}")


def guard(args: argparse.Namespace) -> None:
    spec = json.loads(args.config.read_text(encoding="utf-8"))
    settings = spec["guard"]
    if args.from_run:
        rows = [row for row in load_rows(args.from_run) if row["setup"] == args.setup and row["model"] in settings["models"]
                and row["case"] in spec["fixtures"]["train"]]
        verdict = behavior_verdict(rows, None, settings)
        print(f"guard (from run): {verdict}; reproduced_first={sum(bool(row['reproduced_first']) for row in rows)}/{len(rows)}")
        raise SystemExit({"pass": 0, "fail": 1, "second-stage": 1, "infrastructure": 4}[verdict])

    candidate = (REPO_ROOT / spec["skill"]).read_text(encoding="utf-8")
    base = git("show", f"{args.base}:{spec['skill']}")
    has_parent = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "HEAD~1"], cwd=REPO_ROOT, capture_output=True).returncode == 0
    previous = git("show", f"HEAD~1:{spec['skill']}") if has_parent else base
    original = git("show", f"{spec.get('original_commit') or spec['base_commit']}:{spec['skill']}")
    changed = [line for line in git("diff", "--name-only", args.base).splitlines() if line.strip()]
    failures = static_guard(candidate=candidate, base=base, previous=previous, original=original, changed_files=changed,
                            guard=settings, rules=spec["load_bearing"], frontmatter=spec["frontmatter_sha256"],
                            regions=spec.get("editable_regions"), anchors=spec.get("report_anchors"))
    print(f"size {skill_size(candidate)} (original {skill_size(original)}, base {skill_size(base)}, previous {skill_size(previous)})")
    added = new_words(normalized_body(candidate), normalized_body(original), normalized_body(base))
    print(f"new words: {', '.join(added) or 'none'}")
    if failures:
        print("guard: static fail\n- " + "\n- ".join(failures))
        raise SystemExit(2)
    if args.measured:
        measured = [measure_dir(args.out_root, text) / "measure.json" for text in (candidate, base)]
        if not all(path.is_file() for path in measured):
            print(f"guard: infrastructure; no measure run for {', '.join(str(path.parent) for path in measured if not path.is_file())}")
            raise SystemExit(4)
        rows, base_rows = (json.loads(path.read_text(encoding="utf-8"))["rows"] for path in measured)
        verdict, reasons = brevity_verdict(rows, base_rows, settings)
        print(f"guard: {verdict}; score {statistics.mean(row['total'] for row in rows):.1f} vs base "
              f"{statistics.mean(row['total'] for row in base_rows):.1f}; report {pooled_mean(rows, 'final_report_chars'):.0f} vs base "
              f"{pooled_mean(base_rows, 'final_report_chars'):.0f} chars" + "".join(f"\n- {reason}" for reason in reasons))
        raise SystemExit({"pass": 0, "fail": 1, "infrastructure": 4}[verdict])

    args.out_root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    cache_file = args.out_root / "cache.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.is_file() else {}
    if not args.no_cache and cache.get(digest, {}).get("verdict") == "pass":
        print(f"guard: pass (cached result for this text from {cache[digest]['run']})")
        raise SystemExit(0)

    ledger = Ledger(args.ledger, args.budget_usd)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run = args.out_root / f"guard-{stamp}-{digest[:8]}"
    stages: list[list[dict]] = []
    verdict = "second-stage"
    with tempfile.TemporaryDirectory(prefix="hygiene-candidate-") as temp:
        skill_file = Path(temp) / "SKILL.md"
        skill_file.write_text(candidate, encoding="utf-8")
        session_args = argparse.Namespace(check="fixtures", out=run, max_turns=settings["max_turns"], timeout=args.timeout,
                                          jobs=args.jobs, retries=1, plugins=stage_plugins(skill_file),
                                          clean_config=bool(settings.get("clean_config")))
        (run / "targets").mkdir(parents=True)
        try:
            while verdict == "second-stage":
                round_no = len(stages) + 1
                plan = [(model, case, "invoked", round_no) for model in settings["models"] for case in spec["fixtures"]["train"]]
                stages.append(run_plan(session_args, fixture_job, plan, ledger))
                if any(str(row["error"]).startswith("budget") for row in stages[-1]):
                    raise SystemExit(3)
                verdict = behavior_verdict(stages[0], stages[1] if len(stages) > 1 else None, settings)
        finally:
            shutil.rmtree(session_args.plugins["clean"].parent, ignore_errors=True)
    rows = [row for stage in stages for row in stage]
    report = {"verdict": verdict, "skill_sha256": digest, "size": skill_size(candidate), "stages": len(stages),
              "reproduced_first": sum(bool(row["reproduced_first"]) for row in rows), "sessions": len(rows),
              "unresolved": sum(not (row["fixed"] and row["protected_files_ok"]) for row in rows),
              "cost_usd": sum(row["cost_usd"] or 0 for row in rows), "rows": rows}
    (run / "guard.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if verdict == "pass":
        cache[digest] = {"verdict": verdict, "run": str(run)}
        cache_file.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    print(f"guard: {verdict}; reproduced_first={report['reproduced_first']}/{report['sessions']} unresolved={report['unresolved']} "
          f"stages={report['stages']} cost=${report['cost_usd']:.2f} ledger=${ledger.spent():.2f}. Wrote {run / 'guard.json'}")
    raise SystemExit({"pass": 0, "fail": 1, "infrastructure": 4}[verdict])


def measure_dir(out_root: Path, text: str) -> Path:
    return out_root / f"measure-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"


def run_measure(spec: dict, text: str, args: argparse.Namespace) -> dict:
    """Run and grade the spec's measure sessions for one SKILL.md text; cached by the text's hash."""
    settings, run = spec["measure"], measure_dir(args.out_root, text)
    done = run / "measure.json"
    if done.is_file():
        return json.loads(done.read_text(encoding="utf-8"))
    ledger = Ledger(args.ledger, args.budget_usd)
    shutil.rmtree(run, ignore_errors=True)  # a previous attempt that never finished
    (run / "targets").mkdir(parents=True)
    with contextlib.redirect_stdout(sys.stderr), tempfile.TemporaryDirectory(prefix="hygiene-candidate-") as temp:
        skill_file = Path(temp) / "SKILL.md"
        skill_file.write_text(text, encoding="utf-8")
        session_args = argparse.Namespace(check="fixtures", out=run, max_turns=settings["max_turns"], timeout=args.timeout,
                                          jobs=args.jobs, retries=1, plugins=stage_plugins(skill_file), clean_config=False)
        try:
            plan = [(model, case, "invoked", round_no) for round_no in range(1, settings["rounds"] + 1)
                    for model in settings["models"] for case in spec["fixtures"]["train"]]
            rows = run_plan(session_args, fixture_job, plan, ledger)
        finally:
            shutil.rmtree(session_args.plugins["clean"].parent, ignore_errors=True)
        (run / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        if any(str(row["error"]).startswith("budget") for row in rows):
            raise SystemExit(3)
        if any(not row["completed"] or row["error"] for row in rows):
            raise SystemExit(4)
        grades = grade_all(rows, lambda row: grade_job(settings["judge"], row, args.timeout, ledger, False, run.name), args.jobs, 1)
        if any("error" in grade for grade in grades):
            raise SystemExit(4)
    for row, grade in zip(rows, grades):
        row.update(total=grade["total"], categories=grade["categories"], rubric_flags=grade["rubric_flags"],
                   judge_cost_usd=grade.get("judge_cost_usd"))
    payload = {"skill_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "size": skill_size(text),
               "metric": pooled_mean(rows, "final_report_chars"), "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "rows": rows}
    done.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def measure(args: argparse.Namespace) -> None:
    spec = json.loads(args.config.read_text(encoding="utf-8"))
    text = (args.text or REPO_ROOT / spec["skill"]).read_text(encoding="utf-8")
    payload = run_measure(spec, text, args)
    rows = payload["rows"]
    print(f"measure: report {payload['metric']:.1f} chars (pooled); score {statistics.mean(row['total'] for row in rows):.1f}; "
          f"capped {sum(row['total'] <= 72 for row in rows)}; sessions {len(rows)}; run {measure_dir(args.out_root, text)}",
          file=sys.stderr)
    print(f"{payload['metric']:.1f}")


def compare(args: argparse.Namespace) -> None:
    spec = json.loads(args.config.read_text(encoding="utf-8"))
    original = [row for run in args.original for row in load_rows(run)]
    candidate = [row for run in args.candidate for row in load_rows(run)]
    ungraded = [key for rows in (original, candidate) for key in [(row["model"], row["case"]) for row in rows if row.get("total") is None]]
    if ungraded:
        raise SystemExit(f"rows without a grade: {ungraded}")
    result = compare_arms(original, candidate, spec["final"], spec["fixtures"]["holdout"])
    result["init_fingerprints"] = {arm: {model: sorted({str(row.get("init_fingerprint")) for row in rows if row["model"] == model})
                                         for model in sorted({row["model"] for row in rows})}
                                   for arm, rows in (("original", original), ("candidate", candidate))}
    if args.original_skill and args.candidate_skill:
        before, after = args.original_skill.read_text(encoding="utf-8"), args.candidate_skill.read_text(encoding="utf-8")
        reduction = 1 - skill_size(after) / skill_size(before)
        result["size"] = {"original": skill_size(before), "candidate": skill_size(after), "reduction": reduction}
        result["criteria"]["AC1"] = (reduction >= spec["final"]["min_size_reduction"]
                                     and frontmatter_sha256(after) == frontmatter_sha256(before) == spec["frontmatter_sha256"])
    print(json.dumps({key: value for key, value in result.items() if key != "criteria"}, indent=2, default=str))
    print("\n| Criterion | Met |\n| --- | --- |")
    for criterion, met in sorted(result["criteria"].items()):
        print(f"| {criterion} | {'yes' if met else 'NO'} |")
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="check", required=True)
    def budget(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--ledger", type=Path, help="JSON-lines file that records every session's reported cost.")
        sub.add_argument("--budget-usd", type=float, help="Refuse new sessions once the ledger total could pass this cap.")

    for name in ("fixtures", "triggers"):
        sub = commands.add_parser(name)
        budget(sub)
        sub.add_argument("--out", type=Path, required=True, help="New directory outside this repository for targets, logs, and results.")
        sub.add_argument("--models", nargs="+", default=["haiku", "sonnet", "opus"], help="Claude Code model aliases or ids.")
        sub.add_argument("--setups", nargs="+", help="Default: available invoked (fixtures), description claude-md (triggers).")
        sub.add_argument("--fixture", action="append", dest="fixtures", help="Fixture id for the fixtures check; repeatable.")
        sub.add_argument("--rounds", type=int, default=1)
        sub.add_argument("--jobs", type=int, default=4, help="Sessions to run at once.")
        sub.add_argument("--max-turns", type=int, help="Default: 40 for fixtures, 8 for triggers.")
        sub.add_argument("--timeout", type=int, default=900, help="Seconds per session and per fixture test run.")
        sub.add_argument("--retries", type=int, default=0, help="Re-run a session that broke before finishing, up to this many times.")
        sub.add_argument("--skill-file", type=Path, help="SKILL.md text to stage as the code-hygiene skill instead of this checkout's.")
        sub.add_argument("--clean-config", action="store_true", help="Give every session a fresh, empty CLAUDE_CONFIG_DIR.")
    sub = commands.add_parser("grade")
    budget(sub)
    sub.add_argument("--run", type=Path, required=True, help="Output directory of a finished fixtures run.")
    sub.add_argument("--judge", default="opus", help="Model alias or id for the blind PASS-100 judge.")
    sub.add_argument("--jobs", type=int, default=4)
    sub.add_argument("--timeout", type=int, default=600)
    sub.add_argument("--retries", type=int, default=1, help="Ask the judge again when its reply breaks the rubric's rules.")
    sub.add_argument("--clean-config", action="store_true", help="Give every judge call a fresh, empty CLAUDE_CONFIG_DIR.")
    sub.add_argument("--from-grades", action="store_true", help="Rebuild the result files from the run's grades.json; no judge calls.")
    sub = commands.add_parser("size")
    sub.add_argument("path", type=Path)
    sub = commands.add_parser("metrics")
    sub.add_argument("--run", type=Path, required=True, help="Output directory of a finished fixtures run.")
    sub = commands.add_parser("guard")
    budget(sub)
    sub.add_argument("--config", type=Path, required=True, help="Token-diet spec JSON.")
    sub.add_argument("--base", default="HEAD", help="Git ref of the loop base; changes are measured against it.")
    sub.add_argument("--out-root", type=Path, default=Path(tempfile.gettempdir()) / "hygiene-guard")
    sub.add_argument("--from-run", type=Path, help="Evaluate the behavioral stage on a finished fixtures run instead.")
    sub.add_argument("--setup", default="invoked", help="Setup to read with --from-run.")
    sub.add_argument("--no-cache", action="store_true", help="Run sessions even if this exact text passed before.")
    sub.add_argument("--measured", action="store_true", help="Judge-based guard from the cached measure runs of the candidate and base.")
    sub.add_argument("--jobs", type=int, default=6)
    sub.add_argument("--timeout", type=int, default=900)
    sub = commands.add_parser("measure")
    budget(sub)
    sub.add_argument("--config", type=Path, required=True, help="Spec JSON with a measure section.")
    sub.add_argument("--text", type=Path, help="SKILL.md to measure. Default: this checkout's code-hygiene/SKILL.md.")
    sub.add_argument("--out-root", type=Path, default=Path(tempfile.gettempdir()) / "hygiene-measure")
    sub.add_argument("--jobs", type=int, default=6)
    sub.add_argument("--timeout", type=int, default=900)
    sub = commands.add_parser("compare")
    sub.add_argument("--config", type=Path, required=True, help="Token-diet spec JSON.")
    sub.add_argument("--original", type=Path, nargs="+", required=True, help="Graded fixtures runs of the original skill.")
    sub.add_argument("--candidate", type=Path, nargs="+", required=True, help="Graded fixtures runs of the candidate skill.")
    sub.add_argument("--original-skill", type=Path, help="Original SKILL.md, for the size criterion.")
    sub.add_argument("--candidate-skill", type=Path, help="Candidate SKILL.md, for the size criterion.")
    sub.add_argument("--out", type=Path, help="Write the full comparison as JSON here.")
    args = parser.parse_args()
    if args.check == "size":
        print(skill_size(args.path.read_text(encoding="utf-8")))
    else:
        {"grade": grade, "metrics": metrics, "guard": guard, "compare": compare, "measure": measure}.get(args.check, run_sessions)(args)


if __name__ == "__main__":
    main()
