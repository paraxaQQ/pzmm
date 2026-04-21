from __future__ import annotations

import unittest

from core.error_diff import compute_diff
from core.inspector import ConsoleReport, ModError


def _entry(mod_id: str, msg: str, *, sev: str = "error", occ: int = 1, kind: str = "runtime") -> ModError:
    return ModError(
        mod_id=mod_id,
        mod_name=mod_id,
        severity=sev,
        message=msg,
        file="",
        line=0,
        occurrence_count=occ,
        kind=kind,
    )


class ErrorDiffTests(unittest.TestCase):
    def test_since_last_growth_and_resolution(self):
        prev = ConsoleReport(
            errors=[_entry("a", "boom", occ=1)],
            warns=[_entry("a", "warn", sev="warn", occ=2)],
        )
        curr = ConsoleReport(
            errors=[_entry("a", "boom", occ=3), _entry("b", "new", occ=1)],
            warns=[],
        )
        out = compute_diff(prev, curr, prev)
        grew = out["since_last"]["new_or_grew"]
        resolved = out["since_last"]["resolved_or_shrank"]

        self.assertEqual(2, grew["issue_count"])
        self.assertEqual(3, grew["occurrence_delta"])  # boom +2, new +1
        self.assertEqual(1, resolved["issue_count"])
        self.assertEqual(2, resolved["occurrence_delta"])  # warn removed

    def test_since_startup_uses_baseline(self):
        baseline = ConsoleReport(errors=[_entry("a", "old", occ=2)], warns=[])
        prev = ConsoleReport(errors=[_entry("a", "old", occ=2)], warns=[])
        curr = ConsoleReport(
            errors=[_entry("a", "old", occ=2), _entry("a", "fresh", occ=1)],
            warns=[],
        )
        out = compute_diff(prev, curr, baseline)
        startup = out["since_startup"]["new_or_grew"]
        self.assertEqual(1, startup["issue_count"])
        self.assertEqual(1, startup["occurrence_delta"])


if __name__ == "__main__":
    unittest.main()

