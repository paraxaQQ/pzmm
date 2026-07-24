# Changelog

## Unreleased

- Added a local heuristic malware scanner for mods: new Mod Security tab, scan mode (manual / on startup / after workshop download), warn-or-block policy, per-mod scan from the Mods tab context menu, and result caching keyed by mod content fingerprint.
- Expanded the AI Assistant from 2 to 8 providers: Anthropic, OpenAI, Google Gemini, xAI Grok, DeepSeek, Mistral, OpenRouter, and local Ollama (no key required). Existing saved keys migrate automatically.
- Refreshed model lists to July 2026 (Claude Sonnet 5 / Opus 4.8, GPT-5.6, Gemini 3.6, DeepSeek V4, Grok 4.x); the model box stays editable for any custom ID.

## v0.3 - 2026-05-02

- Updated AI Assistant model dropdowns and fresh-install defaults to reflect current OpenAI and Anthropic model names.
- Added an in-app Steam Workshop browser tab for Project Zomboid with Steam-only navigation, popout support, Steam client status, and quick rescan.
- Kept the embedded Workshop browser privacy-scoped: pzmm does not read, autofill, or persist Steam browser data.
- Opened Steam client protocol links externally so Workshop actions can hand off to the running Steam client.
