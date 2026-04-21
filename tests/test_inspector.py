from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from core import inspector
from core.mods import ModInfo


_TMP_ROOT = Path.cwd() / "_tmp_test_runs"
_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _new_tmp_dir(prefix: str) -> Path:
    p = _TMP_ROOT / f"{prefix}-{uuid.uuid4().hex[:10]}"
    p.mkdir(parents=True, exist_ok=False)
    return p


class InspectorTests(unittest.TestCase):
    def _tmp_dir(self) -> Path:
        p = _new_tmp_dir("inspector")
        self.addCleanup(lambda: shutil.rmtree(p, ignore_errors=True))
        return p

    def _write_console(self, text: str) -> Path:
        p = self._tmp_dir() / "console.txt"
        p.write_text(text, encoding="utf-8")
        return p

    def _dummy_mod(self, root: Path, mod_id: str, name: str) -> ModInfo:
        mod_dir = root / mod_id
        (mod_dir / "media" / "lua").mkdir(parents=True, exist_ok=True)
        (mod_dir / "mod.info").write_text(f"id={mod_id}\nname={name}\n", encoding="utf-8")
        return ModInfo(id=mod_id, name=name, path=mod_dir)

    def test_generic_line_inherits_recent_mod_context(self):
        console = "\n".join([
            'ERROR: General > Lua((MOD:Airdrops)).Airdrops > Exception thrown',
            'ERROR: General > LuaManager.getFunctionObject > no such function "FR_create_blank_part"',
            'WARN : General > SpriteConfig.initObjectInfo > Invalid SpriteConfig object!',
        ])
        p = self._write_console(console)

        report = inspector.parse_console(p, {"Airdrops": "Airdrops"})

        self.assertEqual(2, len(report.errors))
        self.assertEqual(1, len(report.warns))
        self.assertTrue(any("no such function" in e.message for e in report.errors))
        self.assertTrue(any(getattr(e, "attribution", "") == "inferred" for e in report.errors))
        self.assertTrue(any(getattr(e, "attribution", "") == "direct" for e in report.errors))
        for e in report.errors:
            self.assertEqual("airdrops", e.mod_id)
            self.assertEqual("Airdrops", e.mod_name)
        self.assertEqual("__unattributed__", report.warns[0].mod_id)
        self.assertEqual("unattributed", getattr(report.warns[0], "attribution", ""))

    def test_pre_stack_lines_are_captured(self):
        console = "\n".join([
            'function: testA -- file: media/lua/client/A.lua line #91',
            'ERROR: General > Lua((MOD:Airdrops)).Airdrops > Exception thrown',
        ])
        p = self._write_console(console)

        report = inspector.parse_console(p, {"Airdrops": "Airdrops"})
        self.assertEqual(1, len(report.errors))
        err = report.errors[0]
        self.assertEqual(91, err.line)
        self.assertTrue(any("file: media/lua/client/A.lua" in s for s in err.stack))

    def test_run_inspection_filters_to_active_mods(self):
        root = self._tmp_dir()
        active = self._dummy_mod(root, "Airdrops", "Airdrops")

        console = "\n".join([
            'ERROR: General > Lua((MOD:OtherMod)).Other > Exception thrown',
            'ERROR: General > Lua((MOD:Airdrops)).Airdrops > Exception thrown',
        ])
        p = root / "console.txt"
        p.write_text(console, encoding="utf-8")

        report, _ = inspector.run_inspection([active], p)
        self.assertEqual(1, len(report.errors))
        self.assertEqual("airdrops", report.errors[0].mod_id)

    def test_exception_thrown_uses_cause_and_aggregates_occurrences(self):
        console = "\n".join([
            "ERROR: General > Lua((MOD:Airdrops)).Airdrops > Exception thrown",
            "Caused by: java.lang.IllegalStateException: Not in debug",
            "ERROR: General > Lua((MOD:Airdrops)).Airdrops > Exception thrown",
            "Caused by: java.lang.IllegalStateException: Not in debug",
            "ERROR: General > Lua((MOD:Airdrops)).Airdrops > Exception thrown",
            "java.lang.RuntimeException: __sub not defined",
        ])
        p = self._write_console(console)

        report = inspector.parse_console(p, {"Airdrops": "Airdrops"})
        self.assertEqual(2, len(report.errors))
        msgs = sorted(e.message for e in report.errors)
        self.assertTrue(any("IllegalStateException" in m for m in msgs))
        self.assertTrue(any("RuntimeException" in m for m in msgs))

        by_msg = {e.message: e for e in report.errors}
        self.assertEqual(
            2,
            next(e.occurrence_count for m, e in by_msg.items() if "IllegalStateException" in m),
        )
        self.assertEqual(
            1,
            next(e.occurrence_count for m, e in by_msg.items() if "RuntimeException" in m),
        )

    def test_flush_error_message_noise_is_captured_and_grouped(self):
        console = "\n".join([
            "ERROR: General > Lua((MOD:Airdrops)).Airdrops > Exception thrown",
            "ERROR: General > KahluaThread.flushErrorMessage > dumping Lua stack trace",
            "ERROR: General > Lua((MOD:Airdrops)).Airdrops > Exception thrown",
            "ERROR: General > KahluaThread.flushErrorMessage > dumping Lua stack trace",
        ])
        p = self._write_console(console)

        report = inspector.parse_console(p, {"Airdrops": "Airdrops"})
        self.assertEqual(2, len(report.errors))
        by_kind = {e.kind: e for e in report.errors}
        self.assertIn("lua_runtime", by_kind)
        self.assertIn("engine_noise", by_kind)
        self.assertEqual(2, by_kind["lua_runtime"].occurrence_count)
        self.assertEqual(2, by_kind["engine_noise"].occurrence_count)

    def test_exception_cause_chain_includes_wrapper_and_root_cause(self):
        console = "\n".join([
            "ERROR: General > Lua((MOD:Airdrops)).Airdrops > Exception thrown",
            "java.lang.reflect.InvocationTargetException",
            "    at java.base/java.lang.reflect.Method.invoke(Unknown Source)",
            "Caused by: java.lang.IllegalStateException: Not in debug",
        ])
        p = self._write_console(console)

        report = inspector.parse_console(p, {"Airdrops": "Airdrops"})
        self.assertEqual(1, len(report.errors))
        err = report.errors[0]
        self.assertIn("InvocationTargetException", err.cause_chain)
        self.assertIn("IllegalStateException: Not in debug", err.cause_chain)

    def test_generic_script_warning_kept_as_unattributed_with_file_hint(self):
        console = "\n".join([
            "WARN : Script > ScriptModule.CreateFromTokenPP > unknown script object \"--template\" in 'media/scripts/commonitems/damnglobal/template_damnglobal.txt'",
        ])
        p = self._write_console(console)

        report = inspector.parse_console(p, {"Airdrops": "Airdrops"})
        self.assertEqual(0, len(report.errors))
        self.assertEqual(1, len(report.warns))
        warn = report.warns[0]
        self.assertEqual("__unattributed__", warn.mod_id)
        self.assertEqual("media/scripts/commonitems/damnglobal/template_damnglobal.txt", warn.file)
        self.assertEqual("unattributed", warn.attribution)

    def test_run_inspection_reattributes_no_such_function_by_symbol_index(self):
        root = self._tmp_dir()
        mod = self._dummy_mod(root, "FRUsedCarsAlpha", "FR Used Cars")
        script = mod.path / "media" / "scripts" / "vehicles" / "foo.txt"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            "vehicle testcar {\n"
            "  part Door {\n"
            "    create = FR_create_blank_part,\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )

        p = self._write_console(
            'ERROR: General > LuaManager.getFunctionObject > no such function "FR_create_blank_part"'
        )
        report, _ = inspector.run_inspection([mod], p)
        self.assertEqual(1, len(report.errors))
        err = report.errors[0]
        self.assertEqual("frusedcarsalpha", err.mod_id)
        self.assertEqual("FR Used Cars", err.mod_name)
        self.assertEqual("inferred", err.attribution)

    def test_run_inspection_reattributes_vehicle_warning_by_vehicle_id(self):
        root = self._tmp_dir()
        mod = self._dummy_mod(root, "FRUsedCarsAlpha", "FR Used Cars")
        script = mod.path / "media" / "scripts" / "vehicles" / "bar.txt"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            "vehicle 69charger500\n"
            "{\n"
            "}\n",
            encoding="utf-8",
        )

        p = self._write_console(
            'WARN : General > VehicleScript.Loaded > vehicle "69charger500" extents != physicsChassisShape'
        )
        report, _ = inspector.run_inspection([mod], p)
        self.assertEqual(1, len(report.warns))
        warn = report.warns[0]
        self.assertEqual("frusedcarsalpha", warn.mod_id)
        self.assertEqual("FR Used Cars", warn.mod_name)
        self.assertEqual("inferred", warn.attribution)

    def test_run_inspection_reattributes_by_file_hint(self):
        root = self._tmp_dir()
        mod = self._dummy_mod(root, "SKITTLE_LongTermPreservation", "Long Term Preservation")
        script = mod.path / "media" / "scripts" / "items" / "items_dried.txt"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("module Base { }", encoding="utf-8")

        p = self._write_console(
            "WARN : Script > ScriptModule.CreateFromTokenPP > unknown script object \"import\" in 'media/scripts/items/items_dried.txt'"
        )
        report, _ = inspector.run_inspection([mod], p)
        self.assertEqual(1, len(report.warns))
        warn = report.warns[0]
        self.assertEqual("skittle_longtermpreservation", warn.mod_id)
        self.assertEqual("Long Term Preservation", warn.mod_name)
        self.assertEqual("inferred", warn.attribution)


if __name__ == "__main__":
    unittest.main()

