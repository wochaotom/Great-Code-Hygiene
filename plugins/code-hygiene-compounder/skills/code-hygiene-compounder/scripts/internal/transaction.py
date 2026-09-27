"""Staged skill replacement with a scoped recovery journal."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Callable

from internal.evidence import FOLDED_SKIP_NAMES, reject_excluded_directories, tree_digest, unsafe_link


def journal_path(current: Path) -> Path:
    return current.parent / f".{current.name}.promotion-journal.json"


def scoped(path: Path, parent: Path, prefix: str) -> Path:
    absolute = path.absolute()
    if absolute.parent != parent.absolute() or not os.path.normcase(absolute.name).startswith(os.path.normcase(prefix)) or unsafe_link(absolute):
        raise ValueError(f"transaction path is outside scope: {path}")
    return absolute


def remove_tree(path: Path, parent: Path, prefix: str) -> None:
    scoped(path, parent, prefix)
    if path.exists():
        shutil.rmtree(path)


def write_journal(path: Path, payload: dict, *, exclusive: bool = False) -> None:
    content = json.dumps(payload, indent=2, sort_keys=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            if unsafe_link(path):
                raise ValueError(f"unsafe transaction journal: {path}")
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def check_runtime_data(path: Path) -> None:
    if unsafe_link(path):
        raise ValueError(f"unsafe excluded runtime data: {path}")
    if path.is_dir():
        def fail(error: OSError) -> None:
            raise error

        for root, dirs, files in os.walk(path, onerror=fail):
            for name in dirs + files:
                child = Path(root) / name
                if unsafe_link(child):
                    raise ValueError(f"unsafe excluded runtime data: {child}")
    elif not path.is_file():
        raise ValueError(f"unsupported excluded runtime data: {path}")


def runtime_directories(root: Path) -> list[Path]:
    found: list[Path] = []

    def fail(error: OSError) -> None:
        raise error

    for current, dirs, _ in os.walk(root, onerror=fail):
        for name in list(dirs):
            if name.casefold() in FOLDED_SKIP_NAMES:
                found.append(Path(current) / name)
                dirs.remove(name)
    return found


def move_runtime_data(source: Path, destination_root: Path, after_move: Callable[[], None] | None = None) -> None:
    for child in runtime_directories(source):
        check_runtime_data(child)
        destination = destination_root / child.relative_to(source)
        if destination.exists() or unsafe_link(destination):
            raise ValueError(f"excluded runtime data exists in both trees: {child.relative_to(source)}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(child, destination)
        if after_move:
            after_move()


def ensure_no_runtime_data(path: Path) -> None:
    if path.exists() and runtime_directories(path):
        raise ValueError(f"runtime data remains in backup: {path}")


def apply_transaction(candidate: Path, current: Path, expected_current_fingerprint: str, expected_candidate_fingerprint: str, after_phase: Callable[[str], None] | None = None, evidence_bundle_sha256: str | None = None) -> Path:
    if evidence_bundle_sha256 is not None and (len(evidence_bundle_sha256) != 64 or any(char not in "0123456789abcdef" for char in evidence_bundle_sha256)):
        raise ValueError("invalid evidence bundle hash")
    if unsafe_link(candidate) or unsafe_link(current):
        raise ValueError("link or junction transaction root")
    reject_excluded_directories(candidate)
    current = current.absolute()
    journal = journal_path(current)
    if journal.exists():
        raise RuntimeError(f"interrupted transaction must be recovered first: {journal}")
    if tree_digest(candidate) != expected_candidate_fingerprint:
        raise ValueError("approved candidate fingerprint changed before installation")
    if tree_digest(current) != expected_current_fingerprint:
        raise ValueError("approved baseline fingerprint changed before installation")
    candidate, current = candidate.resolve(strict=True), current.resolve(strict=True)
    if candidate == current or candidate in current.parents or current in candidate.parents:
        raise ValueError("candidate and current overlap")
    if unsafe_link(candidate) or unsafe_link(current):
        raise ValueError("link or junction transaction root")
    journal = journal_path(current)
    parent = current.parent
    token = uuid.uuid4().hex
    prefix = f".{current.name}.promotion-"
    stage = scoped(parent / f"{prefix}stage-{token}", parent, prefix)
    backup = scoped(parent / f"{prefix}backup-{token}", parent, prefix)
    claimed = False
    try:
        state = {
            "version": 1,
            "current": str(current),
            "stage": str(stage),
            "backup": str(backup),
            "current_fingerprint": expected_current_fingerprint,
            "candidate_fingerprint": expected_candidate_fingerprint,
            "evidence_bundle_sha256": evidence_bundle_sha256,
            "phase": "staging",
        }
        write_journal(journal, state, exclusive=True)
        claimed = True
        shutil.copytree(candidate, stage, ignore=lambda directory, names: {
            name for name in names if name.casefold() in FOLDED_SKIP_NAMES and (Path(directory) / name).is_dir()
        })
        if tree_digest(stage) != expected_candidate_fingerprint:
            raise ValueError("staged candidate fingerprint mismatch")
        state["phase"] = "prepared"
        write_journal(journal, state)
        if after_phase:
            after_phase("prepared")
        if tree_digest(current) != expected_current_fingerprint:
            remove_tree(stage, parent, prefix)
            journal.unlink()
            raise ValueError("approved baseline fingerprint changed before swap")
        os.replace(current, backup)
        state["phase"] = "backed_up"
        write_journal(journal, state)
        if tree_digest(backup) != expected_current_fingerprint:
            os.replace(backup, current)
            remove_tree(stage, parent, prefix)
            journal.unlink()
            raise ValueError("approved baseline fingerprint changed during swap")
        if after_phase:
            after_phase("backed_up")
        os.replace(stage, current)
        state["phase"] = "installed"
        write_journal(journal, state)
        if after_phase:
            after_phase("installed")
        move_runtime_data(backup, current, lambda: after_phase("runtime_moved") if after_phase else None)
        if tree_digest(current) != expected_candidate_fingerprint:
            raise ValueError("installed candidate fingerprint mismatch")
        state["phase"] = "committed"
        write_journal(journal, state)
        if after_phase:
            after_phase("committed")
        ensure_no_runtime_data(backup)
        journal.unlink()
        return backup
    except BaseException:
        if not claimed or not journal.exists():
            remove_tree(stage, parent, prefix)
        raise


def recover_transaction(current: Path, report: dict | None = None) -> Path | None:
    if unsafe_link(current):
        raise ValueError("link or junction transaction root")
    current = current.absolute()
    current = current.parent.resolve(strict=True) / current.name
    journal = journal_path(current)
    if not journal.is_file() or unsafe_link(journal):
        raise ValueError(f"no safe transaction journal: {journal}")
    state = json.loads(journal.read_text(encoding="utf-8"))
    parent = current.parent
    recorded_current = Path(state.get("current", "")).absolute()
    if state.get("version") != 1 or recorded_current != current or recorded_current.parent != parent or state.get("phase") not in {"staging", "prepared", "backed_up", "installed", "committed"}:
        raise ValueError("transaction journal target mismatch")
    current = recorded_current
    prefix = f".{current.name}.promotion-"
    stage = scoped(Path(state["stage"]), parent, prefix)
    backup = scoped(Path(state["backup"]), parent, prefix)
    if state["phase"] == "staging":
        if backup.exists() or not current.exists() or tree_digest(current) != state.get("current_fingerprint"):
            raise ValueError("staging state changed; recovery requires manual inspection")
        remove_tree(stage, parent, prefix)
        journal.unlink()
        if report is not None:
            report.update(action="cleared_staging", phase=state["phase"], backup=str(backup), journal_state=state)
        return None
    if state["phase"] == "committed":
        if not current.exists() or tree_digest(current) != state.get("candidate_fingerprint"):
            raise ValueError("installed skill changed since installation; recovery requires manual inspection")
        ensure_no_runtime_data(backup)
        remove_tree(stage, parent, prefix)
        journal.unlink()
        if report is not None:
            report.update(action="commit_closed", phase=state["phase"], backup=str(backup), journal_state=state)
        return backup if backup.exists() else None
    if backup.exists():
        if tree_digest(backup) != state.get("current_fingerprint"):
            raise ValueError("backup fingerprint mismatch; recovery requires manual inspection")
        if current.exists():
            if tree_digest(current) != state.get("candidate_fingerprint"):
                raise ValueError("installed skill changed since installation; recovery requires manual inspection")
            move_runtime_data(current, backup)
            discarded = scoped(parent / f"{prefix}discard-{uuid.uuid4().hex}", parent, prefix)
            os.replace(current, discarded)
        else:
            discarded = None
        os.replace(backup, current)
        if discarded:
            remove_tree(discarded, parent, prefix)
        action = "rolled_back"
    elif not current.exists() or tree_digest(current) != state.get("current_fingerprint"):
        raise ValueError("original skill is unavailable; recovery requires manual inspection")
    else:
        action = "cleared_prepared"
    remove_tree(stage, parent, prefix)
    journal.unlink()
    if report is not None:
        report.update(action=action, phase=state["phase"], backup=str(backup), journal_state=state)
    return None
