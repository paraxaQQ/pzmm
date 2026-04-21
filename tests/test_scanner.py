from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from core.mods import ModInfo
from core.scanner import scan_file_conflicts, solve_load_order


_TMP_ROOT = Path.cwd() / "_tmp_test_runs"
_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _new_tmp_dir(prefix: str) -> Path:
    p = _TMP_ROOT / f"{prefix}-{uuid.uuid4().hex[:10]}"
    p.mkdir(parents=True, exist_ok=False)
    return p


def _make_mod(root: Path, mod_id: str, name: str, files: dict[str, str], requires: list[str] | None = None) -> ModInfo:
    mod_dir = root / mod_id
    (mod_dir / "media").mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        f = mod_dir / "media" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    (mod_dir / "mod.info").write_text(f"id={mod_id}\nname={name}\n", encoding="utf-8")
    return ModInfo(id=mod_id, name=name, path=mod_dir, requires=list(requires or []))


class ScannerTests(unittest.TestCase):
    def _tmp_root(self) -> Path:
        p = _new_tmp_dir("scanner")
        self.addCleanup(lambda: shutil.rmtree(p, ignore_errors=True))
        return p

    def test_identical_files_do_not_count_as_conflicts(self):
        root = self._tmp_root()

        m1 = _make_mod(root, "A", "A", {"lua/shared/Test.lua": "print('same')"})
        m2 = _make_mod(root, "B", "B", {"lua/shared/Test.lua": "print('same')"})

        conflicts = scan_file_conflicts([m1, m2])
        self.assertEqual([], conflicts)

    def test_different_files_count_as_conflicts(self):
        root = self._tmp_root()

        m1 = _make_mod(root, "A", "A", {"lua/shared/Test.lua": "print('one')"})
        m2 = _make_mod(root, "B", "B", {"lua/shared/Test.lua": "print('one')"})
        m3 = _make_mod(root, "C", "C", {"lua/shared/Test.lua": "print('two')"})

        conflicts = scan_file_conflicts([m1, m2, m3])
        self.assertEqual(1, len(conflicts))
        self.assertEqual("media/lua/shared/test.lua", conflicts[0].rel_path)
        self.assertEqual(["A", "B", "C"], [m.id for m in conflicts[0].providers])
        self.assertEqual("C", conflicts[0].winner.id)

    def test_non_conflict_extensions_are_ignored(self):
        root = self._tmp_root()

        m1 = _make_mod(root, "A", "A", {"textures/icon.png": "abc"})
        m2 = _make_mod(root, "B", "B", {"textures/icon.png": "xyz"})

        conflicts = scan_file_conflicts([m1, m2])
        self.assertEqual([], conflicts)

    def test_solve_load_order_respects_dependencies(self):
        root = self._tmp_root()

        a = _make_mod(root, "A", "A", {}, requires=[])
        b = _make_mod(root, "B", "B", {}, requires=["A"])
        c = _make_mod(root, "C", "C", {}, requires=["B"])

        graph = solve_load_order([c, b, a])
        self.assertEqual(["A", "B", "C"], graph.order)
        self.assertEqual([], graph.cycles)


if __name__ == "__main__":
    unittest.main()

