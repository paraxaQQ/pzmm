"""Safe read/write helpers for Zomboid's modmanager-mods.txt."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from core import backups


@dataclass
class WriteResult:
    path: Path
    backup_path: Path | None
    created: bool


def _replace_mod_line(current: str, new_mod_line: str) -> str:
    lines = current.splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        if ";" in line and not line.startswith("VERSION"):
            out.append(new_mod_line)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(new_mod_line)
    return "\n".join(out) + "\n"


def write_modmanager_mods(
    path: Path,
    mod_ids: list[str],
    *,
    session_id: str = "modmanager-ui",
    record_manifest: bool = True,
) -> WriteResult:
    """Write active mod IDs to modmanager-mods.txt with backup + atomic replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    mod_line = ";".join(mod_ids)
    existed = path.exists()
    before = path.read_text(encoding="utf-8", errors="ignore") if existed else ""
    after = _replace_mod_line(before, mod_line) if existed else f"VERSION=1\n{mod_line}\n"

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path: Path | None = None
    if existed:
        backup_path = path.with_suffix(path.suffix + f".pzmm.bak-{ts}")
        shutil.copy2(path, backup_path)

    tmp = path.with_suffix(path.suffix + f".tmp-{uuid4().hex[:8]}")
    tmp.write_text(after, encoding="utf-8")
    tmp.replace(path)

    if record_manifest:
        backups.record(backups.BackupEntry(
            ts=datetime.now().isoformat(timespec="seconds"),
            session_id=session_id,
            path=str(path.resolve()),
            backup_path=str(backup_path.resolve()) if backup_path is not None else None,
            operation="overwrite" if existed else "create",
            size_before=len(before.encode("utf-8")),
            size_after=len(after.encode("utf-8")),
        ))

    return WriteResult(path=path, backup_path=backup_path, created=not existed)

