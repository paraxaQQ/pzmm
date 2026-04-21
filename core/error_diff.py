"""Scan-to-scan error diff helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def issue_key(entry) -> tuple[str, str, str, str, str, int]:
    """Stable identity for one logical issue bucket."""
    return (
        str(getattr(entry, "mod_id", "") or ""),
        str(getattr(entry, "severity", "") or ""),
        str(getattr(entry, "kind", "") or ""),
        str(getattr(entry, "message", "") or ""),
        str(getattr(entry, "file", "") or ""),
        int(getattr(entry, "line", 0) or 0),
    )


def _occ(entry) -> int:
    return max(1, int(getattr(entry, "occurrence_count", 1) or 1))


def _to_map(report) -> dict[tuple[str, str, str, str, str, int], tuple[Any, int]]:
    out: dict[tuple[str, str, str, str, str, int], tuple[Any, int]] = {}
    if report is None:
        return out
    for e in list(getattr(report, "errors", [])) + list(getattr(report, "warns", [])):
        out[issue_key(e)] = (e, _occ(e))
    return out


@dataclass
class DiffSlice:
    keys: set[tuple[str, str, str, str, str, int]]
    issue_count: int
    occurrence_delta: int


def _compute_growth(
    prev_map: dict[tuple[str, str, str, str, str, int], tuple[Any, int]],
    curr_map: dict[tuple[str, str, str, str, str, int], tuple[Any, int]],
) -> DiffSlice:
    keys: set[tuple[str, str, str, str, str, int]] = set()
    issue_count = 0
    occurrence_delta = 0
    for k, (_entry, curr_occ) in curr_map.items():
        prev_occ = prev_map.get(k, (None, 0))[1]
        if curr_occ > prev_occ:
            keys.add(k)
            issue_count += 1
            occurrence_delta += (curr_occ - prev_occ)
    return DiffSlice(keys=keys, issue_count=issue_count, occurrence_delta=occurrence_delta)


def _compute_resolved(
    prev_map: dict[tuple[str, str, str, str, str, int], tuple[Any, int]],
    curr_map: dict[tuple[str, str, str, str, str, int], tuple[Any, int]],
) -> DiffSlice:
    keys: set[tuple[str, str, str, str, str, int]] = set()
    issue_count = 0
    occurrence_delta = 0
    for k, (_entry, prev_occ) in prev_map.items():
        curr_occ = curr_map.get(k, (None, 0))[1]
        if curr_occ < prev_occ:
            keys.add(k)
            issue_count += 1
            occurrence_delta += (prev_occ - curr_occ)
    return DiffSlice(keys=keys, issue_count=issue_count, occurrence_delta=occurrence_delta)


def compute_diff(previous_report, current_report, startup_baseline_report) -> dict:
    """Compute diff slices used by the Errors tab and status messages."""
    prev_map = _to_map(previous_report)
    curr_map = _to_map(current_report)
    base_map = _to_map(startup_baseline_report)

    since_last_new = _compute_growth(prev_map, curr_map)
    since_last_resolved = _compute_resolved(prev_map, curr_map)
    since_startup_new = _compute_growth(base_map, curr_map)

    return {
        "since_last": {
            "new_or_grew": {
                "keys": since_last_new.keys,
                "issue_count": since_last_new.issue_count,
                "occurrence_delta": since_last_new.occurrence_delta,
            },
            "resolved_or_shrank": {
                "keys": since_last_resolved.keys,
                "issue_count": since_last_resolved.issue_count,
                "occurrence_delta": since_last_resolved.occurrence_delta,
            },
        },
        "since_startup": {
            "new_or_grew": {
                "keys": since_startup_new.keys,
                "issue_count": since_startup_new.issue_count,
                "occurrence_delta": since_startup_new.occurrence_delta,
            },
        },
    }

