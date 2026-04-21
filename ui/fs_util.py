"""Open folders / files in the system file manager or in an external editor."""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path


def open_folder(path: Path) -> tuple[bool, str]:
    """Open `path` in the OS file manager. Returns (ok, message)."""
    path = Path(path)
    if not path.exists():
        return False, f"path does not exist: {path}"
    target = str(path if path.is_dir() else path.parent)
    try:
        if sys.platform.startswith("win"):
            # Using os.startfile dodges shell quoting issues entirely.
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return True, target
    except Exception as e:
        return False, str(e)


def _detect_default_editor() -> str | None:
    """Best-effort fallback editor detection on Windows."""
    if sys.platform.startswith("win"):
        # Notepad++ common install paths
        candidates = [
            Path(r"C:\Program Files\Notepad++\notepad++.exe"),
            Path(r"C:\Program Files (x86)\Notepad++\notepad++.exe"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        # PATH-based: notepad++ on PATH, else plain notepad
        for name in ("notepad++.exe", "notepad++", "notepad.exe"):
            p = shutil.which(name)
            if p:
                return p
        return "notepad.exe"
    # Non-Windows: let the OS pick via xdg-open / open.
    return None


def open_in_editor(path: Path, editor_cmd: str = "") -> tuple[bool, str]:
    """Open `path` in an external text editor. Returns (ok, message).

    If `editor_cmd` is empty, falls back to a detected default
    (Notepad++ then Notepad on Windows, xdg-open/open elsewhere).
    """
    path = Path(path)
    if not path.exists():
        return False, f"file does not exist: {path}"
    if not path.is_file():
        return False, f"not a file: {path}"

    cmd = (editor_cmd or "").strip() or _detect_default_editor()
    try:
        if cmd:
            subprocess.Popen([cmd, str(path)])
        else:
            # macOS / Linux: let the desktop environment pick.
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        return True, cmd or "(system default)"
    except FileNotFoundError:
        return False, f"editor not found: {cmd}"
    except Exception as e:
        return False, str(e)
