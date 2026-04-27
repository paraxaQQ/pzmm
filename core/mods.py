"""Mod enumeration from workshop and local directories."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

_RE_PZ_VERSION = re.compile(r'(?<!\d)(4[12](?:\.\d+){0,2})(?!\d)')


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
    mod_types: list[str] = field(default_factory=list)


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


def _read_small_text(path: Path, limit: int = 256_000) -> str:
    try:
        with path.open("rb") as f:
            data = f.read(limit)
        return data.decode("utf-8", errors="ignore").lower()
    except Exception:
        return ""


def detect_mod_types(mod_root: Path, kv: dict[str, str] | None = None) -> list[str]:
    """
    Best-effort PZ mod content tags for GUI filtering.

    This intentionally returns multiple tags because real mods often bundle maps,
    scripts, Lua, tiles, sounds, and compatibility patches together.
    """
    tags: set[str] = set()
    kv = kv or {}
    name_blob = " ".join(
        str(v).lower() for v in (
            kv.get("id", ""),
            kv.get("name", ""),
            kv.get("description", ""),
        )
    )
    if any(word in name_blob for word in ("compat", "compatibility", "patch", "fix")):
        tags.add("Patch")
    if any(word in name_blob for word in ("api", "core", "dependency", "framework", "library", "required")):
        tags.add("Dependency")

    media = mod_root / "media"
    if not media.exists():
        return ["Dependency"] if "Dependency" in tags else ["Unknown"]

    script_text_parts: list[str] = []
    lua_text_parts: list[str] = []

    for path in media.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(media).as_posix().lower()
        suffix = path.suffix.lower()

        if rel.startswith("maps/"):
            tags.add("Maps")
        if rel.startswith("texturepacks/") or "tiledefinitions" in rel:
            tags.add("Tiles")
        if rel.startswith(("textures/", "models_x/", "models/")) or suffix in {".png", ".dds"}:
            if path.name.lower() != "poster.png":
                tags.add("Textures")
        if rel.startswith(("scripts/vehicles/", "scripts/vehicle")):
            tags.add("Vehicles")
        if rel.startswith(("clothing/", "scripts/clothing/")):
            tags.add("Clothing")
        if rel.startswith(("sound/", "sounds/", "fmod/")) or suffix in {".bank", ".ogg", ".wav"}:
            tags.add("Sounds")
        if rel.startswith(("ui/", "lua/client/ui/")):
            tags.add("UI")
        if rel.startswith(("anims/", "animsets/", "actiongroups/")):
            tags.add("Animations")
        if rel.startswith("lua/shared/translate/") or "/translate/" in rel:
            tags.add("Translations")
        if rel.startswith("lua/"):
            tags.add("Lua")
            if suffix == ".lua" and len(lua_text_parts) < 60:
                lua_text_parts.append(_read_small_text(path, 64_000))
        if rel.startswith("scripts/") and suffix in {".txt", ".xml"} and len(script_text_parts) < 80:
            script_text_parts.append(_read_small_text(path, 96_000))

    script_blob = "\n".join(script_text_parts)
    lua_blob = "\n".join(lua_text_parts)

    if " type = weapon" in script_blob or "displaycategory = weapon" in script_blob:
        tags.add("Weapons")
    if " vehicle " in script_blob or "module vehicles" in script_blob:
        tags.add("Vehicles")
    if "item " in script_blob:
        tags.add("Items")
    if "recipe " in script_blob or " evolvedrecipe " in script_blob:
        tags.add("Recipes")
    if "bodylocation" in script_blob or "clothingitem" in script_blob:
        tags.add("Clothing")
    if "traitfactory.addtrait" in lua_blob:
        tags.add("Traits")
    if "professionfactory.addprofession" in lua_blob:
        tags.add("Professions")

    if not tags and kv.get("require") and not script_blob:
        tags.add("Framework")

    preferred = [
        "Maps", "Vehicles", "Weapons", "Items", "Clothing", "Traits",
        "Professions", "Recipes", "Tiles", "Textures", "Sounds",
        "Animations", "UI", "Translations", "Lua", "Patch", "Dependency",
        "Framework",
    ]
    ordered = [tag for tag in preferred if tag in tags]
    return ordered or ["Unknown"]


def _ver_key(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def _infer_pz_version(mod_info_path: Path, kv: dict[str, str]) -> str:
    explicit = (kv.get("pzversion", "") or "").strip()
    if explicit:
        return explicit

    candidates: set[str] = set()

    # Folder names often include the build marker, e.g. "42.15.2".
    for part in mod_info_path.parts:
        for m in _RE_PZ_VERSION.finditer(part):
            candidates.add(m.group(1))

    # Common versioned subfolder layout: <mod>/42/... or <mod>/42.16/...
    base = mod_info_path.parent
    try:
        for child in base.iterdir():
            if not child.is_dir():
                continue
            for m in _RE_PZ_VERSION.finditer(child.name):
                candidates.add(m.group(1))
    except Exception:
        pass

    if not candidates:
        return "?"
    return sorted(candidates, key=_ver_key)[-1]


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
                    pz_version=_infer_pz_version(best, kv),
                    authors=kv.get("authors", kv.get("author", "")),
                    workshop_id=workshop_item.name,
                    source="workshop",
                    requires=_parse_requires(kv),
                    mod_types=detect_mod_types(best.parent, kv),
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
                pz_version=_infer_pz_version(mod_info_path, kv),
                authors=kv.get("authors", kv.get("author", "")),
                source="local",
                requires=_parse_requires(kv),
                mod_types=detect_mod_types(mod_info_path.parent, kv),
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
