"""Path sandbox — enforces that AI file tools can only touch allowed roots.

Two root lists:
  - readable: where the AI may read (includes the Zomboid user folder, for logs)
  - writable: where the AI may write (mod folders only — never the Zomboid root)

Writes additionally:
  - get a timestamped backup (.pzmm.bak-<ts>)
  - go through a confirmation callback unless `trusted` is True
  - are refused if `protect_game_data` is True and the path touches Saves /
    Sandbox Presets / ActiveMods*
  - are recorded in the backup manifest so the user can revert them later
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core import backups as backups_mod


class SandboxError(Exception):
    pass


# File extensions we refuse to write to, even inside an allowed root.
_DENY_WRITE_EXT = {
    ".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".ps1", ".sh",
    ".msi", ".scr", ".pyd", ".jar", ".class",
}

# Game-data guard: segment/prefix rules.
_DENIED_EXACT_SEGMENTS = {"saves", "sandbox presets"}
_DENIED_PREFIXES       = ("activemods",)

# Soft size limits — the confirmation dialog is the real gate, these just
# stop a runaway from exhausting memory / disk.
MAX_READ_BYTES  = 2 * 1024 * 1024       # 2 MB
MAX_WRITE_BYTES = 512 * 1024            # 512 KB


# ── Confirmation callback signature ─────────────────────────────────────────────
# ConfirmCallback(path: Path, old: str, new: str) -> (approved: bool, trust: bool)
#   approved: user clicked Approve (or Approve+Trust)
#   trust:    user wants to skip confirmation for the rest of this session
ConfirmCallback = Callable[[Path, str, str], tuple[bool, bool]]


class Sandbox:
    def __init__(
        self,
        readable_roots: list[Path],
        writable_roots: list[Path],
        *,
        protect_game_data: bool = True,
        trusted: bool = False,
        confirm_write: Optional[ConfirmCallback] = None,
        session_id: str = "",
    ):
        self.readable: list[Path] = self._resolve_roots(readable_roots)
        self.writable: list[Path] = self._resolve_roots(writable_roots)
        self.protect_game_data = protect_game_data
        self.trusted = trusted
        self.confirm_write = confirm_write
        self.session_id = session_id

    @staticmethod
    def _resolve_roots(roots: list[Path]) -> list[Path]:
        out: list[Path] = []
        seen: set[Path] = set()
        for r in roots:
            try:
                p = Path(r).resolve()
            except Exception:
                continue
            if p in seen:
                continue
            if p.exists() and p.is_dir():
                out.append(p)
                seen.add(p)
        return out

    def has_roots(self) -> bool:
        return bool(self.readable)

    def describe_roots(self) -> str:
        lines = ["Readable:"]
        lines.extend(f"  - {r}" for r in self.readable) if self.readable else lines.append("  (none)")
        lines.append("Writable:")
        if self.writable:
            lines.extend(f"  - {r}" for r in self.writable)
        else:
            lines.append("  (none)")
        return "\n".join(lines)

    # ── path resolution ─────────────────────────────────────────────────────

    def _resolve(self, raw: str) -> Path:
        if not raw or not isinstance(raw, str):
            raise SandboxError("empty path")
        try:
            return Path(raw).expanduser().resolve()
        except Exception as e:
            raise SandboxError(f"invalid path: {e}")

    def resolve_read(self, raw: str) -> Path:
        p = self._resolve(raw)
        for root in self.readable:
            try:
                p.relative_to(root)
                return p
            except ValueError:
                continue
        raise SandboxError(
            f"path '{p}' is outside the readable roots.\n{self.describe_roots()}"
        )

    def resolve_write(self, raw: str) -> Path:
        p = self._resolve(raw)
        # Must land inside a writable root
        ok = False
        for root in self.writable:
            try:
                p.relative_to(root)
                ok = True
                break
            except ValueError:
                continue
        if not ok:
            raise SandboxError(
                f"path '{p}' is not inside any writable root.\n{self.describe_roots()}"
            )
        # Extension guard
        if p.suffix.lower() in _DENY_WRITE_EXT:
            raise SandboxError(f"writing files of type '{p.suffix}' is not allowed")
        # Game-data guard
        if self.protect_game_data and self._is_protected(p):
            raise SandboxError(
                "write blocked by the game-data guard "
                "(Saves / Sandbox Presets / ActiveMods). "
                "Disable 'Protect game data' in Settings if you really mean this."
            )
        return p

    @staticmethod
    def _is_protected(p: Path) -> bool:
        for part in p.parts:
            lp = part.lower()
            if lp in _DENIED_EXACT_SEGMENTS:
                return True
            for pref in _DENIED_PREFIXES:
                if lp.startswith(pref):
                    return True
        return False


# ── Tool implementations ────────────────────────────────────────────────────────

def tool_read_file(sandbox: Sandbox, path: str) -> str:
    p = sandbox.resolve_read(path)
    if not p.exists():
        raise SandboxError(f"file not found: {p}")
    if not p.is_file():
        raise SandboxError(f"not a file: {p}")
    size = p.stat().st_size
    if size > MAX_READ_BYTES:
        raise SandboxError(f"file too large ({size} bytes, max {MAX_READ_BYTES})")
    return p.read_text(encoding="utf-8", errors="replace")


def tool_list_dir(sandbox: Sandbox, path: str) -> str:
    p = sandbox.resolve_read(path)
    if not p.exists():
        raise SandboxError(f"directory not found: {p}")
    if not p.is_dir():
        raise SandboxError(f"not a directory: {p}")
    entries = []
    for child in sorted(p.iterdir(), key=lambda c: (c.is_file(), c.name.lower())):
        tag = "D" if child.is_dir() else "F"
        size = "" if child.is_dir() else f"  {child.stat().st_size}B"
        entries.append(f"  [{tag}] {child.name}{size}")
    if not entries:
        return f"(empty) {p}"
    return f"{p}\n" + "\n".join(entries)


def tool_write_file(sandbox: Sandbox, path: str, content: str) -> str:
    p = sandbox.resolve_write(path)

    data = content.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        raise SandboxError(f"content too large ({len(data)} bytes, max {MAX_WRITE_BYTES})")
    if not p.parent.exists():
        raise SandboxError(f"parent directory does not exist: {p.parent}")

    old_content = ""
    if p.exists():
        try:
            old_content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            old_content = "(binary or unreadable — existing file will be overwritten)"

    # Confirmation (skipped if trusted)
    if not sandbox.trusted:
        if sandbox.confirm_write is None:
            raise SandboxError("writes require confirmation but no confirmer is wired up")
        approved, trust = sandbox.confirm_write(p, old_content, content)
        if trust:
            sandbox.trusted = True
        if not approved:
            raise SandboxError("user denied the write")

    # Backup any pre-existing file
    backup_path: Optional[Path] = None
    if p.exists():
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = p.with_suffix(p.suffix + f".pzmm.bak-{ts}")
        try:
            backup_path.write_bytes(p.read_bytes())
        except Exception as e:
            raise SandboxError(f"could not create backup: {e}")

    existed = p.exists()
    p.write_bytes(data)

    # Record in the backup manifest so the user can revert later.
    try:
        backups_mod.record(backups_mod.BackupEntry(
            ts=datetime.now().isoformat(timespec="seconds"),
            session_id=sandbox.session_id,
            path=str(p),
            backup_path=str(backup_path) if backup_path is not None else None,
            operation="overwrite" if existed else "create",
            size_before=len(old_content.encode("utf-8")) if existed else 0,
            size_after=len(data),
        ))
    except Exception:
        # Never let a manifest failure break the actual write.
        pass

    msg = f"{'overwrote' if existed else 'created'} {p} ({len(data)} bytes)"
    if backup_path is not None:
        msg += f"\nbackup: {backup_path.name}"
    msg += "\n(tracked in history — revert via AI tab → History)"
    return msg
