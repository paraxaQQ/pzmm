from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from core import porting


_TMP_ROOT = Path.cwd() / "_tmp_test_runs"
_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _new_tmp_dir(prefix: str) -> Path:
    p = _TMP_ROOT / f"{prefix}-{uuid.uuid4().hex[:10]}"
    p.mkdir(parents=True, exist_ok=False)
    return p


class PortingTests(unittest.TestCase):
    def _tmp_dir(self) -> Path:
        p = _new_tmp_dir("porting")
        self.addCleanup(lambda: shutil.rmtree(p, ignore_errors=True))
        return p

    def test_discover_version_layout(self):
        root = self._tmp_dir() / "MyMod"
        (root / "42.13" / "media").mkdir(parents=True, exist_ok=True)
        (root / "42.14" / "media").mkdir(parents=True, exist_ok=True)
        (root / "42.14" / "media" / "a.lua").write_text("-- x", encoding="utf-8")
        (root / "42.13" / "media" / "b.lua").write_text("-- y", encoding="utf-8")

        layout = porting.discover_version_layout(root)
        self.assertEqual(root.resolve(), layout.mod_root.resolve())
        self.assertEqual(["42.13", "42.14"], layout.versions)

    def test_build_plan_counts_missing_and_existing(self):
        root = self._tmp_dir() / "MyMod"
        src = root / "42.14"
        dst = root / "42.16"
        (src / "media" / "lua").mkdir(parents=True, exist_ok=True)
        (dst / "media" / "lua").mkdir(parents=True, exist_ok=True)
        (src / "media" / "lua" / "A.lua").write_text("A", encoding="utf-8")
        (src / "media" / "lua" / "B.lua").write_text("B", encoding="utf-8")
        (dst / "media" / "lua" / "B.lua").write_text("old", encoding="utf-8")

        plan = porting.build_port_plan(root, "42.14", "42.16")
        self.assertEqual(1, len(plan.missing_files))
        self.assertEqual(1, len(plan.existing_files))
        self.assertIn(Path("media/lua/A.lua"), plan.missing_files)
        self.assertIn(Path("media/lua/B.lua"), plan.existing_files)

    def test_execute_port_with_backup_and_manifest(self):
        root = self._tmp_dir() / "MyMod"
        src = root / "42.14"
        dst = root / "42.16"
        (src / "media" / "lua").mkdir(parents=True, exist_ok=True)
        (dst / "media" / "lua").mkdir(parents=True, exist_ok=True)
        (src / "media" / "lua" / "A.lua").write_text("new A", encoding="utf-8")
        (src / "media" / "lua" / "B.lua").write_text("new B", encoding="utf-8")
        (dst / "media" / "lua" / "B.lua").write_text("old B", encoding="utf-8")

        plan = porting.build_port_plan(root, "42.14", "42.16")
        result = porting.execute_port(
            plan,
            copy_only_missing=False,
            overwrite_existing=True,
            create_backup_before_overwrite=True,
        )

        self.assertEqual(2, result.copied_files)
        self.assertEqual(1, result.overwritten_files)
        self.assertIsNotNone(result.backup_path)
        self.assertTrue(result.manifest_path.exists())
        self.assertEqual("new B", (dst / "media" / "lua" / "B.lua").read_text(encoding="utf-8"))

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("42.14", manifest["from_version"])
        self.assertEqual("42.16", manifest["to_version"])
        self.assertEqual(2, manifest["copied_files"])

    def test_execute_port_copy_missing_only_skips_overwrite(self):
        root = self._tmp_dir() / "MyMod"
        src = root / "42.14"
        dst = root / "42.16"
        (src / "media" / "lua").mkdir(parents=True, exist_ok=True)
        (dst / "media" / "lua").mkdir(parents=True, exist_ok=True)
        (src / "media" / "lua" / "A.lua").write_text("new A", encoding="utf-8")
        (src / "media" / "lua" / "B.lua").write_text("new B", encoding="utf-8")
        (dst / "media" / "lua" / "B.lua").write_text("old B", encoding="utf-8")

        plan = porting.build_port_plan(root, "42.14", "42.16")
        result = porting.execute_port(
            plan,
            copy_only_missing=True,
            overwrite_existing=True,  # ignored by option
            create_backup_before_overwrite=True,
        )
        self.assertEqual(1, result.copied_files)
        self.assertEqual(0, result.overwritten_files)
        self.assertEqual("old B", (dst / "media" / "lua" / "B.lua").read_text(encoding="utf-8"))

    def test_clone_mod_root_to_local_creates_copy(self):
        tmp = self._tmp_dir()
        workshop_root = tmp / "workshop_mod"
        (workshop_root / "42.14" / "media" / "lua").mkdir(parents=True, exist_ok=True)
        (workshop_root / "42.14" / "media" / "lua" / "A.lua").write_text("A", encoding="utf-8")
        local_mods = tmp / "local_mods"
        local_mods.mkdir(parents=True, exist_ok=True)

        dest = porting.clone_mod_root_to_local(
            workshop_root / "42.14",
            local_mods,
            preferred_name="My Cool Mod",
        )
        self.assertTrue(dest.exists())
        self.assertTrue((dest / "42.14" / "media" / "lua" / "A.lua").exists())

    def test_export_workshop_ready_copy_excludes_pzmm_artifacts(self):
        tmp = self._tmp_dir()
        mod_root = tmp / "MyMod"
        (mod_root / "42.14" / "media" / "lua").mkdir(parents=True, exist_ok=True)
        (mod_root / "42.14" / "media" / "lua" / "A.lua").write_text("A", encoding="utf-8")
        (mod_root / ".pzmm" / "port-manifests").mkdir(parents=True, exist_ok=True)
        (mod_root / ".pzmm" / "port-manifests" / "x.json").write_text("{}", encoding="utf-8")
        (mod_root / "42.14.pzmm-backup-20260101").mkdir(parents=True, exist_ok=True)

        out_parent = tmp / "exports"
        dest = porting.export_workshop_ready_copy(mod_root, out_parent, preferred_name="My Mod")
        self.assertTrue(dest.exists())
        self.assertTrue((dest / "42.14" / "media" / "lua" / "A.lua").exists())
        self.assertFalse((dest / ".pzmm").exists())
        self.assertFalse((dest / "42.14.pzmm-backup-20260101").exists())


if __name__ == "__main__":
    unittest.main()
