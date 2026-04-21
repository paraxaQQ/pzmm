from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from core import mods


_TMP_ROOT = Path.cwd() / "_tmp_test_runs"
_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _new_tmp_dir(prefix: str) -> Path:
    p = _TMP_ROOT / f"{prefix}-{uuid.uuid4().hex[:10]}"
    p.mkdir(parents=True, exist_ok=False)
    return p


class ModsTests(unittest.TestCase):
    def _tmp_dir(self) -> Path:
        p = _new_tmp_dir("mods")
        self.addCleanup(lambda: shutil.rmtree(p, ignore_errors=True))
        return p

    def test_local_pz_version_inferred_from_folder_name(self):
        root = self._tmp_dir()
        mod_dir = root / "Bandits Improved AI 42.15.2 MP"
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "mod.info").write_text("id=Bandits\nname=Bandits\n", encoding="utf-8")

        out = mods.load_local_mods([root])
        self.assertEqual(1, len(out))
        self.assertEqual("42.15.2", out[0].pz_version)

    def test_local_pz_version_inferred_from_version_subfolder(self):
        root = self._tmp_dir()
        mod_dir = root / "SomeMod"
        vdir = mod_dir / "42.16"
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "mod.info").write_text("id=SomeMod\nname=Some Mod\n", encoding="utf-8")

        out = mods.load_local_mods([root])
        self.assertEqual(1, len(out))
        self.assertEqual("42.16", out[0].pz_version)


if __name__ == "__main__":
    unittest.main()

