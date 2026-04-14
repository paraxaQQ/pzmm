"""Mod enumeration from workshop and local directories."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModInfo:
    id: str
    name: str
    path: Path          # root mod folder (contains mod.info)
    version: str = "?"
    pz_version: str = "?"
    authors: str = ""
    workshop_id: str = ""
    source: str = "workshop"   # "workshop" | "local"
    requires: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _parse_mod_info(mod_info_path: Path) -> dict[str, str]:
    kv: dict[str, str] = {}
    try:
        for line in mod_info_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                k = k.strip().lower()
                v = v.strip()
                if k not in kv:          # first value wins (handles multi-line description)
                    kv[k] = v
    except Exception:
        pass
    return kv


def _parse_requires(kv: dict[str, str]) -> list[str]:
    raw = kv.get("require", "")
    if not raw:
        return []
    return [r.strip() for r in raw.split(",") if r.strip()]


def _find_mod_info_files(root: Path) -> list[Path]:
    """
    Workshop layout:  <workshop_id>/mods/<mod_name>/mod.info
    Local layout:     <mod_name>/mod.info   (inside Zomboid/mods/)
    Also handles versioned sub-dirs like 42/, 42.13/ etc.
    """
    results = []
    if not root.exists():
        return results
    for p in root.rglob("mod.info"):
        results.append(p)
    return results


def _best_mod_info(paths: list[Path]) -> Path:
    """
    Given multiple mod.info files for the same workshop item, pick the one
    from the highest versioned subfolder (e.g. 42.15 > 42.13 > 42 > root).
    """
    def sort_key(p: Path) -> tuple:
        parts = p.parts
        for part in reversed(parts[:-1]):   # walk up, skip "mod.info" itself
            # versioned folder like "42", "42.13", "42.15"
            nums = re.findall(r'\d+', part)
            if nums and part.replace(".", "").isdigit():
                return tuple(int(n) for n in nums)
        return (0,)   # root-level mod.info

    return sorted(paths, key=sort_key)[-1]


def load_workshop_mods(workshop_dirs: list[Path]) -> list[ModInfo]:
    mods: list[ModInfo] = []
    seen_ids: set[str] = set()

    for wdir in workshop_dirs:
        if not wdir.exists():
            continue
        for workshop_item in sorted(wdir.iterdir()):
            if not workshop_item.is_dir():
                continue
            all_infos = _find_mod_info_files(workshop_item)
            if not all_infos:
                continue

            # Group by mod ID, pick best version per ID
            by_id: dict[str, list[Path]] = {}
            for p in all_infos:
                kv = _parse_mod_info(p)
                mid = kv.get("id", "")
                if mid:
                    by_id.setdefault(mid, []).append(p)

            for mod_id, paths in by_id.items():
                if mod_id in seen_ids:
                    continue
                seen_ids.add(mod_id)
                best = _best_mod_info(paths)
                kv = _parse_mod_info(best)
                mods.append(ModInfo(
                    id=mod_id,
                    name=kv.get("name", mod_id),
                    path=best.parent,
                    version=kv.get("modversion", kv.get("version", "?")),
                    pz_version=kv.get("pzversion", "?"),
                    authors=kv.get("authors", kv.get("author", "")),
                    workshop_id=workshop_item.name,
                    source="workshop",
                    requires=_parse_requires(kv),
                ))
    return mods


def load_local_mods(local_dirs: list[Path]) -> list[ModInfo]:
    mods: list[ModInfo] = []
    for ldir in local_dirs:
        if not ldir.exists():
            continue
        for mod_info_path in _find_mod_info_files(ldir):
            kv = _parse_mod_info(mod_info_path)
            mod_id = kv.get("id", "")
            if not mod_id:
                continue
            mods.append(ModInfo(
                id=mod_id,
                name=kv.get("name", mod_id),
                path=mod_info_path.parent,
                version=kv.get("modversion", kv.get("version", "?")),
                pz_version=kv.get("pzversion", "?"),
                authors=kv.get("authors", kv.get("author", "")),
                source="local",
                requires=_parse_requires(kv),
            ))
    return mods


def _parse_mods_txt(path: Path) -> set[str]:
    """Parse a mods.txt / default.txt style file (mod = ID, lines)."""
    ids = set()
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r'\s*mod\s*=\s*(.+?),?\s*$', line)
            if m:
                ids.add(m.group(1).strip())
    except Exception:
        pass
    return ids


def find_most_recent_save(zomboid_root: Path) -> Path | None:
    """Return the mods.txt from the most recently modified save."""
    saves_dir = zomboid_root / "Saves"
    if not saves_dir.exists():
        return None
    candidates = list(saves_dir.rglob("mods.txt"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_active_mod_ids(zomboid_root: Path | None) -> set[str]:
    """
    Find the most recently played save's mods.txt — that's what PZ actually loaded.
    Falls back to default.txt then modmanager-mods.txt.
    """
    if not zomboid_root:
        return set()

    # Most recent save's mods.txt = ground truth
    save_mods = find_most_recent_save(zomboid_root)
    if save_mods:
        ids = _parse_mods_txt(save_mods)
        if ids:
            return ids

    # Fallback: default.txt
    default_txt = zomboid_root / "mods" / "default.txt"
    if default_txt.exists():
        ids = _parse_mods_txt(default_txt)
        if ids:
            return ids

    # Fallback: modmanager-mods.txt
    p = zomboid_root / "Lua" / "modmanager-mods.txt"
    if p.exists():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                if ";" in line and not line.startswith("VERSION"):
                    return {m.strip() for m in line.split(";") if m.strip()}
        except Exception:
            pass

    return set()
