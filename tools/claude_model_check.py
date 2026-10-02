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

Both plugins load from this checkout with --plugin-dir, so nothing is installed.
Skills or plugins already enabled in your Claude Code config also compete; point
CLAUDE_CONFIG_DIR at a clean config to isolate the run. Every run calls the model
and uses your Claude usage.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import json
import shutil
import subprocess
import sys
import tempfile
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
from pass100_runner import load_prompts  # noqa: E402

CLEAN_SKILL = "code-hygiene:code-hygiene"
ALLOWED_TOOLS = "Bash Read Edit Write Glob Grep Skill"
DEFAULT_FIXTURES = ("hyg-006-currency-rounding", "hyg-083-config-precedence")
FIXTURE_SUFFIX = " Work in this repository. The tests in tests/ describe the expected behavior; do not edit or add files under tests/."
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


def claude_executable() -> str:
    executable = shutil.which("claude")
    if executable is None:
        raise SystemExit("claude CLI not found on PATH")
    return executable


def claude_command(model: str, max_turns: int, plugins: bool) -> list[str]:
    command = [claude_executable(), "-p", "--model", model, "--output-format", "stream-json", "--verbose",
               "--max-turns", str(max_turns), "--permission-mode", "acceptEdits", "--allowedTools", ALLOWED_TOOLS]
    if plugins:
        command += ["--plugin-dir", str(REPO_ROOT / "code-hygiene"), "--plugin-dir", str(TRAINER_ROOT)]
    return command


def run_claude(command: list[str], prompt: str, cwd: Path, log: Path, timeout: int) -> dict:
    """Run one session (prompt on stdin, so variadic flags cannot swallow it) and summarize it."""
    try:
        completed = subprocess.run(command, input=prompt, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        stdout, error = completed.stdout, completed.stderr.strip()
    except subprocess.TimeoutExpired as exc:
        stdout, error = exc.stdout or "", f"timed out after {timeout}s"
        stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
    log.write_text(stdout, encoding="utf-8")
    skills: list[str] = []
    result: dict = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "Skill":
                    skills.append(str(block.get("input", {}).get("skill")))
        elif event.get("type") == "result":
            result = event
    return {
        "skills": skills,
        "completed": bool(result),
        "stop_reason": result.get("subtype"),
        "turns": result.get("num_turns"),
        "cost_usd": result.get("total_cost_usd"),
        "final_report": result.get("result", ""),
        "error": error if not result else "",
    }


def task_prompt(item: dict) -> str:
    prompts = {prompt["id"]: prompt["prompt"] for prompt in load_prompts(TRAINER_ROOT / "references" / "eval-prompts.md")}
    return prompts[item["prompt_id"]] + FIXTURE_SUFFIX


def fixture_job(args: argparse.Namespace, model: str, fixture_id: str, setup: str, round_no: int) -> dict:
    item = find_fixture(TRAINER_ROOT / "fixtures", fixture_id)
    prompt = task_prompt(item)
    if setup == "invoked":
        prompt = f"/{CLEAN_SKILL} {prompt}"
    # An opaque folder name keeps the setup and model out of paths the blind judge reads.
    target = args.out / "targets" / f"run-{uuid.uuid4().hex[:12]}"
    copy_fixture_repo(item, target, force=True)
    session = run_claude(claude_command(model, args.max_turns, setup != "none"), prompt, target, target.parent / f"{target.name}.jsonl", args.timeout)
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
    session = run_claude(claude_command(model, args.max_turns, True), prompt, target, target.parent / f"{target.name}.jsonl", args.timeout)
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
    for line in log.read_text(encoding="utf-8").splitlines() if log.is_file() else []:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for block in event.get("message", {}).get("content", []) if event.get("type") == "assistant" else []:
            if block.get("type") == "tool_use":
                tool_input = block.get("input", {})
                detail = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("pattern") or ""
                detail = " ".join(scrub(str(detail), target).split())
                lines.append(f"{len(lines) + 1}. {block.get('name')}: {detail[:200]}")
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


def grade_job(judge: str, row: dict, timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="hygiene-judge-") as workdir:
        command = [claude_executable(), "-p", "--model", judge, "--output-format", "json", "--max-turns", "1",
                   "--disable-slash-commands"]
        completed = subprocess.run(command, input=judge_prompt(row), cwd=workdir, capture_output=True, text=True, timeout=timeout)
    reply = json.loads(completed.stdout) if completed.stdout.strip().startswith("{") else {}
    try:
        return {**parse_judgement(reply.get("result", "")), "judge_cost_usd": reply.get("total_cost_usd")}
    except (ValueError, KeyError, TypeError) as exc:
        return {"error": f"{exc}; stderr: {completed.stderr.strip()[:200]}"}


def grade(args: argparse.Namespace) -> None:
    rows = json.loads((args.run / "results.json").read_text(encoding="utf-8"))
    rows = [row for row in rows if row.get("check") == "fixtures"]
    if not rows:
        raise SystemExit(f"no fixtures results in {args.run}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        grades = list(pool.map(lambda row: grade_job(args.judge, row, args.timeout), rows))
    failed = [(row["setup"], row["model"], row["case"], result["error"]) for row, result in zip(rows, grades) if "error" in result]
    if failed:
        raise SystemExit("judge failures:\n" + "\n".join(map(str, failed)))

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    files: dict[tuple[str, str], Path] = {}
    for setup, model in sorted({(row["setup"], row["model"]) for row in rows}):
        scores = []
        for row, result in zip(rows, grades):
            if (row["setup"], row["model"]) != (setup, model):
                continue
            item = find_fixture(TRAINER_ROOT / "fixtures", row["case"])
            scores.append({"prompt_id": item["prompt_id"], "total": result["total"], "categories": result["categories"],
                           "deductions": result["deductions"], "lessons": [], "resolved": row["fixed"] and row["protected_files_ok"],
                           "cost_usd": row["cost_usd"] or 0})
        payload = {"run_id": f"{setup}-{model}", "run_type": "model-execution", "phase": 0,
                   "prompt_ids": sorted({score["prompt_id"] for score in scores}), "scores": scores,
                   "model": model, "skill_version": commit, "harness": f"claude -p; judge {args.judge}",
                   "started_at": now, "completed_at": now}
        files[(setup, model)] = args.run / f"pass100-{setup}-{model}.json"
        files[(setup, model)].write_text(json.dumps(payload, indent=2), encoding="utf-8")

    scripts, suite = TRAINER_ROOT / "scripts", TRAINER_ROOT / "references" / "eval-prompts.md"
    for path in files.values():
        subprocess.run([sys.executable, "-B", str(scripts / "validate_results.py"), "--results", str(path), "--suite", str(suite)],
                       check=True, capture_output=True, text=True)
    print("| Setup | Model | Average | Resolved |\n| --- | --- | --- | --- |")
    for (setup, model), path in files.items():
        scores = json.loads(path.read_text(encoding="utf-8"))["scores"]
        average = sum(score["total"] for score in scores) / len(scores)
        print(f"| {setup} | {model} | {average:.1f} | {sum(score['resolved'] for score in scores)}/{len(scores)} |")
    for (setup, model), path in files.items():
        if setup != "none" and ("none", model) in files:
            out = args.run / f"analysis-{setup}-vs-none-{model}.json"
            subprocess.run([sys.executable, "-B", str(scripts / "analyze_runs.py"), "--results", str(path),
                            "--baseline", str(files[("none", model)]), "--suite", str(suite), "--out", str(out)],
                           check=True, capture_output=True, text=True)
            print(f"Wrote {out}")
    judge_cost = sum(result.get("judge_cost_usd") or 0 for result in grades)
    print(f"Graded {len(rows)} sessions with {args.judge}; reported judge cost ${judge_cost:.2f}.")


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
    (args.out / "targets").mkdir(parents=True)

    plan = [(model, case, setup, round_no) for round_no in range(1, args.rounds + 1)
            for setup in setups for model in args.models for case in cases]
    rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(job, args, *entry) for entry in plan]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows.append(row)
            print(f"{row['setup']:<11} {row['model']:<10} {row['case']:<34} r{row['round']} loaded_skill={row['loaded_skill']}"
                  + (f" fixed={row['fixed']}" if "fixed" in row else "") + (f" error={row['error']}" if row["error"] else ""), flush=True)

    rows.sort(key=lambda row: (row["setup"], row["model"], row["case"], row["round"]))
    (args.out / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    keys = ("loaded_skill", "fixed", "protected_files_ok") if args.check == "fixtures" else ("loaded_skill",)
    print()
    print("\n\n".join(summarize(rows, args.models, setups, key) for key in keys))
    cost = sum(row["cost_usd"] or 0 for row in rows)
    errors = [row for row in rows if row["error"] or not row["completed"]]
    print(f"\n{len(rows)} sessions, reported cost ${cost:.2f}, {len(errors)} incomplete. Results: {args.out / 'results.json'}")
    if errors:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="check", required=True)
    for name in ("fixtures", "triggers"):
        sub = commands.add_parser(name)
        sub.add_argument("--out", type=Path, required=True, help="New directory outside this repository for targets, logs, and results.")
        sub.add_argument("--models", nargs="+", default=["haiku", "sonnet", "opus"], help="Claude Code model aliases or ids.")
        sub.add_argument("--setups", nargs="+", help="Default: available invoked (fixtures), description claude-md (triggers).")
        sub.add_argument("--fixture", action="append", dest="fixtures", help="Fixture id for the fixtures check; repeatable.")
        sub.add_argument("--rounds", type=int, default=1)
        sub.add_argument("--jobs", type=int, default=4, help="Sessions to run at once.")
        sub.add_argument("--max-turns", type=int, help="Default: 40 for fixtures, 8 for triggers.")
        sub.add_argument("--timeout", type=int, default=900, help="Seconds per session and per fixture test run.")
    sub = commands.add_parser("grade")
    sub.add_argument("--run", type=Path, required=True, help="Output directory of a finished fixtures run.")
    sub.add_argument("--judge", default="opus", help="Model alias or id for the blind PASS-100 judge.")
    sub.add_argument("--jobs", type=int, default=4)
    sub.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    grade(args) if args.check == "grade" else run_sessions(args)


if __name__ == "__main__":
    main()
