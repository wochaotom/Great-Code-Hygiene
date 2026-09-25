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

    def addFailure(self, test, err):
        self.failed_ids.append(test.id())
        super().addFailure(test, err)

    def addError(self, test, err):
        self.error_ids.append(test.id())
        super().addError(test, err)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: unittest_reporter.py TEST_DIRECTORY")
    sys.path.insert(0, str(Path.cwd()))
    suite = unittest.defaultTestLoader.discover(sys.argv[1])
    runner = unittest.TextTestRunner(resultclass=RecordingResult)
    result = runner.run(suite)
    print(PREFIX + json.dumps({
        "framework": "python-unittest",
        "tests_run": result.testsRun,
        "failures": sorted(result.failed_ids),
        "errors": sorted(result.error_ids),
    }, sort_keys=True))
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
