"""Version-folder porting utilities for local mods."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
import shutil
from pathlib import Path


_RE_VERSION = re.compile(r"^\d+(?:\.\d+)*$")


@dataclass
class VersionLayout:
    mod_root: Path
    versions: list[str]


@dataclass
class PortPlan:
    mod_root: Path
    source_dir: Path
    target_dir: Path
    missing_files: list[Path]
    existing_files: list[Path]
    created_dirs: list[Path]

    @property
    def source_count(self) -> int:
        return len(self.missing_files) + len(self.existing_files)


@dataclass
class PortResult:
    copied_files: int
    overwritten_files: int
    backup_path: Path | None
    manifest_path: Path


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _sanitize_name(name: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._ -]+", "", (name or "").strip())
    out = re.sub(r"\s+", " ", out).strip()
    return out or "mod"


def discover_version_layout(mod_path: Path) -> VersionLayout:
    """
    Infer the mod root + version folders from a local mod path.
    If mod_path itself is versioned, treat its parent as root.
    """
    p = mod_path.resolve()
    mod_root = p.parent if _RE_VERSION.match(p.name) else p
    versions: list[str] = []
    if mod_root.exists():
        for child in mod_root.iterdir():
            if not child.is_dir():
                continue
            if not _RE_VERSION.match(child.name):
                continue
            if any(f.is_file() for f in child.rglob("*")):
                versions.append(child.name)
    versions.sort(key=_version_key)
    return VersionLayout(mod_root=mod_root, versions=versions)


def clone_mod_root_to_local(mod_path: Path, local_mods_dir: Path, *, preferred_name: str) -> Path:
    """
    Clone a workshop mod root into a local mods directory and return the new root.
    This never writes back to workshop content.
    """
    layout = discover_version_layout(mod_path)
    source_root = layout.mod_root.resolve()
    local_root = local_mods_dir.resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise ValueError(f"Source mod root does not exist: {source_root}")
    local_root.mkdir(parents=True, exist_ok=True)

    base = _sanitize_name(preferred_name)
    dest = local_root / base
    if dest.exists():
        suffix = 1
        while True:
            cand = local_root / f"{base} ({suffix})"
            if not cand.exists():
                dest = cand
                break
            suffix += 1

    shutil.copytree(source_root, dest)
    return dest


def export_workshop_ready_copy(mod_root: Path, output_parent: Path, *, preferred_name: str) -> Path:
    """
    Export a clean copy suitable for workshop packaging/review.
    Excludes pzmm manifests and backup artifacts.
    """
    source_root = mod_root.resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise ValueError(f"Mod root does not exist: {source_root}")
    out_parent = output_parent.resolve()
    out_parent.mkdir(parents=True, exist_ok=True)

    base = _sanitize_name(preferred_name)
    dest = out_parent / base
    if dest.exists():
        suffix = 1
        while True:
            cand = out_parent / f"{base} ({suffix})"
            if not cand.exists():
                dest = cand
                break
            suffix += 1

    def _ignore(_dir: str, names: list[str]):
        ignored: list[str] = []
        for n in names:
            low = n.lower()
            if low == ".pzmm":
                ignored.append(n)
                continue
            if ".pzmm-backup-" in low:
                ignored.append(n)
                continue
            if low.endswith(".pzmm.bak"):
                ignored.append(n)
                continue
        return ignored

    shutil.copytree(source_root, dest, ignore=_ignore)
    return dest


def build_port_plan(mod_root: Path, from_version: str, to_version: str) -> PortPlan:
    root = mod_root.resolve()
    source_dir = (root / from_version).resolve()
    target_dir = (root / to_version).resolve()

    if not _RE_VERSION.match(from_version):
        raise ValueError("Invalid source version folder name.")
    if not _RE_VERSION.match(to_version):
        raise ValueError("Invalid target version folder name.")
    if from_version == to_version:
        raise ValueError("Source and target versions must be different.")
    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError(f"Source version folder does not exist: {source_dir}")
    if not _is_relative_to(source_dir, root) or not _is_relative_to(target_dir, root):
        raise ValueError("Unsafe path: source/target must stay inside the mod root.")

    missing_files: list[Path] = []
    existing_files: list[Path] = []
    created_dirs: set[Path] = set()

    for src in source_dir.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(source_dir)
        dst = target_dir / rel
        if dst.exists():
            existing_files.append(rel)
        else:
            missing_files.append(rel)
        parent_rel = dst.parent.relative_to(target_dir)
        if parent_rel != Path("."):
            created_dirs.add(parent_rel)

    return PortPlan(
        mod_root=root,
        source_dir=source_dir,
        target_dir=target_dir,
        missing_files=sorted(missing_files),
        existing_files=sorted(existing_files),
        created_dirs=sorted(created_dirs),
    )


def execute_port(
    plan: PortPlan,
    *,
    copy_only_missing: bool,
    overwrite_existing: bool,
    create_backup_before_overwrite: bool,
) -> PortResult:
    if copy_only_missing:
        overwrite_existing = False

    to_copy: list[Path] = list(plan.missing_files)
    if overwrite_existing:
        to_copy.extend(plan.existing_files)

    if not to_copy:
        raise ValueError("Nothing to copy with the current options.")

    root = plan.mod_root.resolve()
    source_dir = plan.source_dir.resolve()
    target_dir = plan.target_dir.resolve()
    if not _is_relative_to(source_dir, root) or not _is_relative_to(target_dir, root):
        raise ValueError("Unsafe path: source/target must stay inside the mod root.")

    backup_path: Path | None = None
    if overwrite_existing and create_backup_before_overwrite and target_dir.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = root / f"{target_dir.name}.pzmm-backup-{stamp}"
        if backup_path.exists():
            raise ValueError(f"Backup path already exists: {backup_path}")
        shutil.copytree(target_dir, backup_path)

    copied = 0
    overwritten = 0
    for rel in to_copy:
        src = source_dir / rel
        dst = target_dir / rel
        if not _is_relative_to(src, source_dir) or not _is_relative_to(dst, target_dir):
            raise ValueError("Unsafe path encountered while copying.")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            overwritten += 1
        shutil.copy2(src, dst)
        copied += 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest_dir = root / ".pzmm" / "port-manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"port-{plan.source_dir.name}-to-{plan.target_dir.name}-{stamp}.json"
    manifest = {
        "timestamp": stamp,
        "mod_root": str(root),
        "from_version": plan.source_dir.name,
        "to_version": plan.target_dir.name,
        "copy_only_missing": bool(copy_only_missing),
        "overwrite_existing": bool(overwrite_existing),
        "create_backup_before_overwrite": bool(create_backup_before_overwrite),
        "copied_files": copied,
        "overwritten_files": overwritten,
        "backup_path": str(backup_path) if backup_path else "",
        "files": [str(p).replace("\\", "/") for p in to_copy],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return PortResult(
        copied_files=copied,
        overwritten_files=overwritten,
        backup_path=backup_path,
        manifest_path=manifest_path,
    )
