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

    def test_detects_multiple_mod_types(self):
        root = self._tmp_dir()
        mod_dir = root / "KitchenSink"
        scripts = mod_dir / "media" / "scripts"
        maps = mod_dir / "media" / "maps" / "NewTown"
        vehicles = mod_dir / "media" / "scripts" / "vehicles"
        scripts.mkdir(parents=True, exist_ok=True)
        maps.mkdir(parents=True, exist_ok=True)
        vehicles.mkdir(parents=True, exist_ok=True)
        (mod_dir / "mod.info").write_text("id=KitchenSink\nname=Kitchen Sink\n", encoding="utf-8")
        (maps / "map.info").write_text("title=NewTown\n", encoding="utf-8")
        (scripts / "weapons.txt").write_text(
            "module Base { item TestRifle { Type = Weapon, DisplayCategory = Weapon, } }",
            encoding="utf-8",
        )
        (vehicles / "cars.txt").write_text("module Vehicles { vehicle TestCar { } }", encoding="utf-8")

        out = mods.load_local_mods([root])
        self.assertEqual(1, len(out))
        self.assertIn("Maps", out[0].mod_types)
        self.assertIn("Weapons", out[0].mod_types)
        self.assertIn("Vehicles", out[0].mod_types)

    def test_unknown_when_no_media_signals(self):
        root = self._tmp_dir()
        mod_dir = root / "Emptyish"
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "mod.info").write_text("id=Emptyish\nname=Emptyish\n", encoding="utf-8")

        out = mods.load_local_mods([root])
        self.assertEqual(["Unknown"], out[0].mod_types)


if __name__ == "__main__":
    unittest.main()

