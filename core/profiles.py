"""Mod profiles — snapshot and restore sets of active mods + load order.

Each profile is a single JSON file at %APPDATA%/pzmm/profiles/<slug>.json:
    {
        "name": "Vanilla+",
        "created": "2026-04-18T14:30:00",
        "updated": "2026-04-18T14:30:00",
        "mod_ids": ["ModA", "ModB", ...],
        "load_order": ["ModA", "ModB", ...]
    }

Profiles are *independent* of config.json — deleting pzmm doesn't nuke them
unless the user wipes the whole %APPDATA%/pzmm tree.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import CONFIG_PATH
from core.modmanager_io import WriteResult, write_modmanager_mods


PROFILES_DIR = CONFIG_PATH.parent / "profiles"


@dataclass
class Profile:
    name:        str
    created:     str
    updated:     str
    mod_ids:     list[str] = field(default_factory=list)
    load_order:  list[str] = field(default_factory=list)


def _slug(name: str) -> str:
    """Filesystem-safe slug. Collisions get a numeric suffix at save time."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    s = s.strip("._-") or "profile"
    return s[:64]


def _ensure_dir() -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR


def _path_for(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.json"


def list_profiles() -> list[Profile]:
    """All profiles, sorted by updated-desc. Silently skips malformed files."""
    if not PROFILES_DIR.exists():
        return []
    out: list[Profile] = []
    for p in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            out.append(Profile(
                name=data.get("name") or p.stem,
                created=data.get("created", ""),
                updated=data.get("updated", ""),
                mod_ids=list(data.get("mod_ids") or []),
                load_order=list(data.get("load_order") or []),
            ))
        except Exception:
            continue
    out.sort(key=lambda pr: pr.updated or pr.created, reverse=True)
    return out


def load(name: str) -> Optional[Profile]:
    """Look up a profile by display name. Returns None if not found."""
    for pr in list_profiles():
        if pr.name == name:
            return pr
    # Also allow slug lookup as a fallback
    slug_path = _path_for(_slug(name))
    if slug_path.exists():
        try:
            data = json.loads(slug_path.read_text(encoding="utf-8"))
            return Profile(
                name=data.get("name") or name,
                created=data.get("created", ""),
                updated=data.get("updated", ""),
                mod_ids=list(data.get("mod_ids") or []),
                load_order=list(data.get("load_order") or []),
            )
        except Exception:
            return None
    return None


def save(name: str, mod_ids: list[str], load_order: list[str],
         overwrite: bool = False) -> Profile:
    """Create or update a profile. If `overwrite=False` and the name already
    exists, appends ' (N)' until unique so we never silently clobber.
    Returns the persisted profile.
    """
    _ensure_dir()
    now = datetime.now().isoformat(timespec="seconds")

    existing = load(name)
    if existing and not overwrite:
        base = name
        n = 2
        while load(f"{base} ({n})"):
            n += 1
        name = f"{base} ({n})"
        existing = None

    created = existing.created if existing else now
    pr = Profile(
        name=name,
        created=created,
        updated=now,
        mod_ids=list(mod_ids),
        load_order=list(load_order),
    )

    # Slug collision handling: if another profile uses our target slug, append.
    slug = _slug(name)
    target = _path_for(slug)
    # If we're updating an existing same-name profile, target already matches.
    # Otherwise, bump slug until unique.
    if target.exists() and (not existing or existing.name != name):
        i = 2
        while _path_for(f"{slug}-{i}").exists():
            i += 1
        target = _path_for(f"{slug}-{i}")

    target.write_text(json.dumps(asdict(pr), indent=2), encoding="utf-8")
    return pr


def delete(name: str) -> bool:
    """Remove a profile by display name. Returns True if something was deleted."""
    if not PROFILES_DIR.exists():
        return False
    for p in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if (data.get("name") or p.stem) == name:
                p.unlink()
                return True
        except Exception:
            continue
    return False


def apply_to_modmanager(profile: Profile, zomboid_root: Path) -> WriteResult:
    """Write the profile's load order to modmanager-mods.txt.

    Mirrors LoadOrderTab._apply_order — replaces the first ';'-separated,
    non-VERSION line. Creates the file if missing.

    Returns write metadata including path + backup info.
    """
    p = zomboid_root / "Lua" / "modmanager-mods.txt"

    # Use load_order if present (dep-sorted), else fall back to mod_ids order.
    ids = profile.load_order or profile.mod_ids
    return write_modmanager_mods(p, ids, session_id=f"profile:{profile.name}")
