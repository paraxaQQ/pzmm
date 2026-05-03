"""User config — API keys, model choice, persisted to %APPDATA%/pzmm/config.json."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path


def _config_dir() -> Path:
    # Windows: %APPDATA%/pzmm  |  Linux/Mac: ~/.config/pzmm
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "pzmm"
    return Path.home() / ".config" / "pzmm"


CONFIG_PATH = _config_dir() / "config.json"


@dataclass
class Config:
    ai_assistant_enabled: bool = False           # hide AI tab unless explicitly enabled
    provider: str = "anthropic"                 # "anthropic" | "openai"
    anthropic_key: str = ""
    openai_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    openai_model: str = "gpt-5.2"
    system_prompt: str = (
        "You are an expert Project Zomboid modder helping debug and fix B42 mods. "
        "You know the Lua API, the B41->B42 breaking changes (getClassFieldVal signature, "
        "ItemBodyLocation string->object, getOrCreateLocation, isDigital() tag system, "
        "mod loading order and versioned subfolders), and the common crash patterns. "
        "When the user attaches errors and source files, give concrete, minimal patches. "
        "Show the exact lines to change, not just prose."
    )
    allow_file_access: bool = False              # gated tool-use: read/write mod files
    ai_trusted_mode: bool = False                 # skip per-write confirmation dialog
    protect_game_data: bool = True                # refuse writes under Saves/ActiveMods/Sandbox Presets
    external_editor: str = ""                      # exe path for "open in editor"; "" = auto-detect
    auto_scan_on_launch: bool = False              # run Scan on startup
    watch_console: bool = True                     # live-refresh Errors when console.txt changes
    color_theme: str = "midnight"                  # ui.style theme key
    last_update_check_ts: float = 0.0             # UTC epoch of last GitHub release ping
    last_known_latest: str = ""                    # latest release tag we saw
    dismissed_update: str = ""                     # tag the user dismissed — don't nag about it again
    history: list[dict] = field(default_factory=list)   # last conversation
    conversation_threads: list[dict] = field(default_factory=list)  # saved AI conversations
    active_conversation_id: str = ""                               # selected AI conversation

    @property
    def active_key(self) -> str:
        return self.anthropic_key if self.provider == "anthropic" else self.openai_key

    @property
    def active_model(self) -> str:
        return self.anthropic_model if self.provider == "anthropic" else self.openai_model


def load() -> Config:
    if not CONFIG_PATH.exists():
        return Config()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cfg = Config()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg
    except Exception:
        return Config()


def save(cfg: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
