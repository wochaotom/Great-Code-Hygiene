"""Run unittest discovery and emit machine-readable TestResult identities."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PREFIX = "CODE_HYGIENE_TEST_RESULT="


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failed_ids: list[str] = []
        self.error_ids: list[str] = []
        self.passed_ids: list[str] = []

    def addSuccess(self, test):
        self.passed_ids.append(test.id())
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.failed_ids.append(test.id())
        super().addFailure(test, err)

    def addError(self, test, err):
        self.error_ids.append(test.id())
        super().addError(test, err)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: unittest_reporter.py TEST_DIRECTORY REPORT_PATH")
    sys.path.insert(0, str(Path.cwd()))
    suite = unittest.defaultTestLoader.discover(sys.argv[1])
    runner = unittest.TextTestRunner(resultclass=RecordingResult)
    result = runner.run(suite)
    report = {
        "framework": "python-unittest",
        "tests_run": result.testsRun,
        "skipped": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "failures": sorted(result.failed_ids),
        "errors": sorted(result.error_ids),
        "passed": sorted(result.passed_ids),
    }
    Path(sys.argv[2]).write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    print(PREFIX + json.dumps(report, sort_keys=True))
    executed = result.testsRun - len(result.skipped) - len(result.expectedFailures)
    return 0 if result.wasSuccessful() and executed > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
