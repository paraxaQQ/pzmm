import json

import pytest

from core import config as config_mod


@pytest.fixture
def cfg_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config_mod, "CONFIG_PATH", path)
    return path


def test_legacy_flat_fields_migrate(cfg_file):
    cfg_file.write_text(json.dumps({
        "provider": "openai",
        "anthropic_key": "sk-ant-old",
        "openai_key": "sk-old",
        "anthropic_model": "claude-sonnet-4-6",
        "openai_model": "gpt-5.2",
    }), encoding="utf-8")
    cfg = config_mod.load()
    assert cfg.provider == "openai"
    assert cfg.api_keys == {"anthropic": "sk-ant-old", "openai": "sk-old"}
    assert cfg.models == {"anthropic": "claude-sonnet-4-6", "openai": "gpt-5.2"}
    assert cfg.active_key == "sk-old"
    assert cfg.active_model == "gpt-5.2"


def test_new_dicts_win_over_legacy(cfg_file):
    cfg_file.write_text(json.dumps({
        "provider": "anthropic",
        "anthropic_key": "sk-ant-old",
        "api_keys": {"anthropic": "sk-ant-new"},
    }), encoding="utf-8")
    cfg = config_mod.load()
    assert cfg.api_keys["anthropic"] == "sk-ant-new"


def test_active_model_falls_back_to_provider_default(cfg_file):
    cfg = config_mod.Config(provider="deepseek")
    assert cfg.active_model == "deepseek-v4-flash"


def test_save_round_trip(cfg_file):
    cfg = config_mod.Config(provider="gemini", api_keys={"gemini": "AIza-x"})
    config_mod.save(cfg)
    loaded = config_mod.load()
    assert loaded.provider == "gemini"
    assert loaded.api_keys == {"gemini": "AIza-x"}
