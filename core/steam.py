"""Steam library and PZ path detection."""
import os
import re
from pathlib import Path

try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

PZ_APP_ID = "108600"


def get_steam_path() -> Path | None:
    if _HAS_WINREG:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            val, _ = winreg.QueryValueEx(key, "SteamPath")
            p = Path(val)
            if p.exists():
                return p
        except Exception:
            pass
    # Fallback: common install locations
    candidates = [
        Path("C:/Program Files (x86)/Steam"),
        Path("C:/Program Files/Steam"),
        Path.home() / ".steam" / "steam",           # Linux
        Path.home() / "Library/Application Support/Steam",  # macOS
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def get_steam_libraries(steam_path: Path) -> list[Path]:
    """Return all steamapps dirs across all Steam library folders."""
    libs = []
    base = steam_path / "steamapps"
    if base.exists():
        libs.append(base)
    vdf = base / "libraryfolders.vdf"
    if vdf.exists():
        text = vdf.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            p = Path(m.group(1).replace("\\\\", "/")) / "steamapps"
            if p.exists() and p not in libs:
                libs.append(p)
    return libs


def find_pz_workshop_dirs() -> list[Path]:
    steam = get_steam_path()
    if not steam:
        return []
    return [
        lib / "workshop" / "content" / PZ_APP_ID
        for lib in get_steam_libraries(steam)
        if (lib / "workshop" / "content" / PZ_APP_ID).exists()
    ]


def find_local_mods_dirs() -> list[Path]:
    candidates = [
        Path.home() / "Zomboid" / "mods",
        Path(os.environ.get("USERPROFILE", "~")) / "Zomboid" / "mods",
    ]
    return list({p for p in candidates if p.exists()})


def find_zomboid_root() -> Path | None:
    for p in [Path.home() / "Zomboid",
               Path(os.environ.get("USERPROFILE", "")) / "Zomboid"]:
        if p.exists():
            return p
    return None
