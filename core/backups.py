"""Track every AI-initiated file write so the user can revert.

Every successful write from the sandbox is appended as a `BackupEntry`
to a JSON manifest next to the app config. `revert()` restores the file
either by copying the `.pzmm.bak-<ts>` backup back on top of the target
(for overwrites) or by deleting the newly-created file (for creates).

Manifest lives at `%APPDATA%/pzmm/backups.json`.
"""
from __future__ import annotations
import json
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from core.config import CONFIG_PATH


MANIFEST_PATH = CONFIG_PATH.parent / "backups.json"


@dataclass
class BackupEntry:
    ts: str                             # ISO timestamp (seconds)
    session_id: str                     # groups writes from one chat session
    path: str                           # absolute path of the file that was written
    backup_path: Optional[str]          # path to .pzmm.bak-... copy, or None if "create"
    operation: str                      # "overwrite" | "create"
    size_before: int
    size_after: int
    reverted: bool = False


def _load_raw() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_raw(entries: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(entries, indent=2), encoding="utf-8"
    )


def all_entries() -> list[BackupEntry]:
    out: list[BackupEntry] = []
    for d in _load_raw():
        try:
            out.append(BackupEntry(**d))
        except Exception:
            continue
    return out


def record(entry: BackupEntry) -> None:
    data = _load_raw()
    data.append(asdict(entry))
    _save_raw(data)


def revert(entry: BackupEntry) -> str:
    """Revert a single write. Returns a human-readable message. Raises on failure."""
    target = Path(entry.path)
    if entry.operation == "create":
        if target.exists():
            target.unlink()
            msg = f"deleted newly-created file: {target}"
        else:
            msg = f"file already gone: {target}"
    else:
        if not entry.backup_path:
            raise RuntimeError("no backup path recorded for overwrite")
        bak = Path(entry.backup_path)
        if not bak.exists():
            raise RuntimeError(f"backup missing on disk: {bak}")
        shutil.copy2(bak, target)
        msg = f"restored {target.name} from {bak.name}"
    _mark_reverted(entry)
    return msg


def _mark_reverted(entry: BackupEntry) -> None:
    data = _load_raw()
    for d in data:
        if d.get("ts") == entry.ts and d.get("path") == entry.path:
            d["reverted"] = True
    _save_raw(data)


def purge_reverted() -> int:
    """Drop already-reverted entries from the manifest. Returns count removed."""
    data = _load_raw()
    keep = [d for d in data if not d.get("reverted")]
    removed = len(data) - len(keep)
    _save_raw(keep)
    return removed
