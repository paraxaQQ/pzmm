from pathlib import Path

import pytest

from core import virus_scanner


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def _make_mod(root: Path, name: str, files: dict[str, str]) -> Path:
    mod = root / name
    for rel, content in files.items():
        p = mod / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return mod


def test_clean_mod_is_safe(tmp_path):
    mod = _make_mod(tmp_path, "CleanMod", {
        "mod.info": "name=Clean\nid=clean",
        "media/lua/client/init.lua": "print('hello')\n",
    })
    result = virus_scanner.scan_mod(mod, mod_id="clean")
    assert result.risk_level == "safe"
    assert result.status == "clean"
    assert result.findings == []


def test_os_execute_flags_high(tmp_path):
    mod = _make_mod(tmp_path, "EvilMod", {
        "media/lua/client/evil.lua": 'os.execute("calc.exe")\n',
    })
    result = virus_scanner.scan_mod(mod, mod_id="evil")
    assert result.risk_level == "high"
    assert any(f.rule == "OS_EXECUTE" for f in result.findings)


def test_blocked_extension_flags_high(tmp_path):
    mod = _make_mod(tmp_path, "ExeMod", {"payloadless/tool.exe": "MZ"})
    result = virus_scanner.scan_mod(mod, mod_id="exe")
    assert result.risk_level == "high"
    assert any(f.rule == "BLOCKED_EXTENSION" for f in result.findings)


def test_cache_hit_and_force(tmp_path):
    mod = _make_mod(tmp_path, "CacheMod", {
        "media/lua/client/a.lua": "local x = 1\n",
    })
    first = virus_scanner.scan_mod(mod, mod_id="cache")
    assert not first.from_cache
    second = virus_scanner.scan_mod(mod, mod_id="cache")
    assert second.from_cache
    forced = virus_scanner.scan_mod(mod, mod_id="cache", force=True)
    assert not forced.from_cache


def test_missing_path_errors(tmp_path):
    result = virus_scanner.scan_mod(tmp_path / "nope", mod_id="missing")
    assert result.risk_level == "error"
    assert result.error
