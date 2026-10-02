#!/usr/bin/env python3
"""Run the hygiene skills through Claude Code on several models and tabulate the results.

Two checks:

  fixtures  Run executable fixtures through `claude -p` and score each target with
            fixture_runner. Setups: `none` (no hygiene plugins), `available` (both
            plugins loaded, request does not name a skill), `invoked` (request starts
            with /code-hygiene:code-hygiene).
  triggers  Send everyday requests that never name the skill and record whether the
            model loads code-hygiene on its own. Setups: `description` (plugins only)
            and `claude-md` (plus a one-line project CLAUDE.md instruction).

Both plugins load from this checkout with --plugin-dir, so nothing is installed.
Skills or plugins already enabled in your Claude Code config also compete; point
CLAUDE_CONFIG_DIR at a clean config to isolate the run. Every run calls the model
and uses your Claude usage.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
TRAINER_ROOT = REPO_ROOT / "code-hygiene-compounder"
sys.path.insert(0, str(TRAINER_ROOT / "scripts"))

from fixture_runner import copy_fixture_repo, find_fixture, run_fixture_target  # noqa: E402
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


def claude_command(model: str, max_turns: int, plugins: bool) -> list[str]:
    executable = shutil.which("claude")
    if executable is None:
        raise SystemExit("claude CLI not found on PATH")
    command = [executable, "-p", "--model", model, "--output-format", "stream-json", "--verbose",
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


def fixture_job(args: argparse.Namespace, model: str, fixture_id: str, setup: str, round_no: int) -> dict:
    item = find_fixture(TRAINER_ROOT / "fixtures", fixture_id)
    prompts = {prompt["id"]: prompt["prompt"] for prompt in load_prompts(TRAINER_ROOT / "references" / "eval-prompts.md")}
    prompt = prompts[item["prompt_id"]] + FIXTURE_SUFFIX
    if setup == "invoked":
        prompt = f"/{CLEAN_SKILL} {prompt}"
    target = args.out / "targets" / f"{setup}-{model}-{fixture_id}-r{round_no}"
    copy_fixture_repo(item, target, force=True)
    session = run_claude(claude_command(model, args.max_turns, setup != "none"), prompt, target, target.parent / f"{target.name}.jsonl", args.timeout)
    score = run_fixture_target(item, target, args.timeout)
    return {"check": "fixtures", "setup": setup, "model": model, "case": fixture_id, "round": round_no,
            "fixed": score["outcome"] == "pass", "protected_files_ok": score["protected_files_ok"],
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("check", choices=("fixtures", "triggers"))
    parser.add_argument("--out", type=Path, required=True, help="New directory outside this repository for targets, logs, and results.")
    parser.add_argument("--models", nargs="+", default=["haiku", "sonnet", "opus"], help="Claude Code model aliases or ids.")
    parser.add_argument("--setups", nargs="+", help="Default: available invoked (fixtures), description claude-md (triggers).")
    parser.add_argument("--fixture", action="append", dest="fixtures", help="Fixture id for the fixtures check; repeatable.")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=4, help="Sessions to run at once.")
    parser.add_argument("--max-turns", type=int, help="Default: 40 for fixtures, 8 for triggers.")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds per session and per fixture test run.")
    args = parser.parse_args()

    args.out = args.out.resolve()
    if args.out == REPO_ROOT or REPO_ROOT in args.out.parents:
        parser.error("--out must be outside the repository")
    if args.out.exists():
        parser.error(f"--out already exists: {args.out}")
    if args.check == "fixtures":
        setups = args.setups or ["available", "invoked"]
        cases, job = args.fixtures or list(DEFAULT_FIXTURES), fixture_job
        allowed, args.max_turns = {"none", "available", "invoked"}, args.max_turns or 40
    else:
        setups = args.setups or ["description", "claude-md"]
        cases, job = list(TRIGGER_REQUESTS), trigger_job
        allowed, args.max_turns = {"description", "claude-md"}, args.max_turns or 8
    if not set(setups) <= allowed:
        parser.error(f"--setups for {args.check} must be from: {', '.join(sorted(allowed))}")
    (args.out / "targets").mkdir(parents=True)

    plan = [(model, case, setup, round_no) for round_no in range(1, args.rounds + 1)
            for setup in setups for model in args.models for case in cases]
    rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(job, args, *entry) for entry in plan]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows.append(row)
            print(f"{row['setup']:<11} {row['model']:<10} {row['case']:<28} r{row['round']} loaded_skill={row['loaded_skill']}"
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


if __name__ == "__main__":
    main()
