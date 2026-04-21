from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from core.modmanager_io import write_modmanager_mods


_TMP_ROOT = Path.cwd() / "_tmp_test_runs"
_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _new_tmp_dir(prefix: str) -> Path:
    p = _TMP_ROOT / f"{prefix}-{uuid.uuid4().hex[:10]}"
    p.mkdir(parents=True, exist_ok=False)
    return p


class ModmanagerIOTests(unittest.TestCase):
    def _tmp_dir(self) -> Path:
        p = _new_tmp_dir("modmanagerio")
        self.addCleanup(lambda: shutil.rmtree(p, ignore_errors=True))
        return p

    def test_overwrite_creates_backup_and_replaces_mod_line(self):
        root = self._tmp_dir()
        p = root / "Lua" / "modmanager-mods.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        original = "VERSION=1\nOldA;OldB\n# keep me\n"
        p.write_text(original, encoding="utf-8")

        wr = write_modmanager_mods(p, ["NewA", "NewB"], record_manifest=False)

        self.assertFalse(wr.created)
        self.assertIsNotNone(wr.backup_path)
        self.assertTrue(wr.backup_path.exists())
        self.assertEqual(original, wr.backup_path.read_text(encoding="utf-8"))

        updated = p.read_text(encoding="utf-8")
        self.assertIn("VERSION=1", updated)
        self.assertIn("NewA;NewB", updated)
        self.assertIn("# keep me", updated)
        self.assertNotIn("OldA;OldB", updated)

    def test_create_new_file_writes_version_and_mod_line(self):
        root = self._tmp_dir()
        p = root / "Lua" / "modmanager-mods.txt"

        wr = write_modmanager_mods(p, ["A", "B", "C"], record_manifest=False)

        self.assertTrue(wr.created)
        self.assertIsNone(wr.backup_path)
        text = p.read_text(encoding="utf-8")
        self.assertEqual("VERSION=1\nA;B;C\n", text)


if __name__ == "__main__":
    unittest.main()

