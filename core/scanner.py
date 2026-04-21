"""File conflict detection and load order solver."""
from __future__ import annotations
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from core.mods import ModInfo


# ── File conflict ─────────────────────────────────────────────────────────────

@dataclass
class FileConflict:
    rel_path: str                      # normalised media/... path
    providers: list[ModInfo]           # all mods supplying this file
    winner: ModInfo | None = None      # last in load order = winner


# Only these extensions produce real gameplay conflicts worth surfacing
_CONFLICT_EXTS = {".lua", ".txt", ".xml", ".json", ".ini"}


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 128), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_file_conflicts(mods: list[ModInfo]) -> list[FileConflict]:
    # rel path -> [(provider mod, concrete file path)]
    path_map: dict[str, list[tuple[ModInfo, Path]]] = defaultdict(list)

    for mod in mods:
        media = mod.path / "media"
        if not media.exists():
            continue
        for f in media.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in _CONFLICT_EXTS:
                continue
            try:
                rel = f.relative_to(mod.path).as_posix().lower()
                path_map[rel].append((mod, f))
            except ValueError:
                pass

    conflicts = []
    for rel, entries in path_map.items():
        if len(entries) <= 1:
            continue

        # If every provider ships byte-identical content, treat it as
        # a duplicate rather than a meaningful conflict.
        hashes: set[str] = set()
        for _, f in entries:
            try:
                hashes.add(_sha1(f))
            except OSError:
                # If hashing fails, keep the item as a conflict (better to
                # over-report than silently hide a potentially real issue).
                hashes.add(f"__io_error__:{f}")
        if len(hashes) <= 1:
            continue

        providers = [mod for mod, _ in entries]
        conflicts.append(FileConflict(
            rel_path=rel,
            providers=providers,
            winner=providers[-1],
        ))

    conflicts.sort(key=lambda c: c.rel_path)
    return conflicts


# ── Dependency graph + Kahn topological sort ─────────────────────────────────

@dataclass
class DepGraph:
    order: list[str]          # sorted mod IDs
    cycles: list[str]         # IDs caught in cycles
    edges: dict[str, list[str]] = field(default_factory=dict)   # id → deps


def solve_load_order(mods: list[ModInfo]) -> DepGraph:
    id_set = {m.id for m in mods}
    in_deg: dict[str, int] = {m.id: 0 for m in mods}
    rdeps: dict[str, list[str]] = defaultdict(list)
    edges: dict[str, list[str]] = {}

    for mod in mods:
        valid_deps = [d for d in mod.requires if d in id_set]
        edges[mod.id] = valid_deps
        for dep in valid_deps:
            rdeps[dep].append(mod.id)
            in_deg[mod.id] += 1

    ready: list[str] = sorted(m.id for m in mods if in_deg[m.id] == 0)
    order: list[str] = []

    while ready:
        cur = ready.pop(0)
        order.append(cur)
        newly_ready: list[str] = []
        for rdep in rdeps[cur]:
            in_deg[rdep] -= 1
            if in_deg[rdep] == 0:
                newly_ready.append(rdep)
        ready = sorted(ready + newly_ready)

    placed = set(order)
    cycles = [m.id for m in mods if m.id not in placed]

    return DepGraph(order=order, cycles=cycles, edges=edges)
