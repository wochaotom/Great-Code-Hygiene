"""Fixed scoring policy shared by result validation and scoring."""

from __future__ import annotations

import math


CATEGORY_KEYS = {
    "correctness": 15,
    "tests": 15,
    "maintainability": 15,
    "security": 10,
    "local_integration": 10,
    "minimal_diff": 10,
    "observability": 10,
    "documentation": 5,
    "dependencies": 5,
    "agent_process": 5,
}
CRITICAL_CATEGORIES = frozenset({"correctness", "tests", "security", "minimal_diff"})
PROMOTION_THRESHOLD = 85.0
RUBRIC_CAPS = {
    "main_behavior_break": 60,
    "risky_change_unverified": 70,
    "feasible_feedback_loop_missing": 72,
    "unrelated_or_user_work_reverted": 75,
    "security_review_missing": 80,
    "important_edge_cases_ignored": 85,
}


def finite_number(value: object, *, integer: bool = False, nonnegative: bool = False) -> bool:
    if isinstance(value, bool):
        return False
    if integer:
        return isinstance(value, int) and (not nonnegative or value >= 0)
    if not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and (not nonnegative or value >= 0)
    except OverflowError:
        return False
