# Changelog

## v0.4 - 2026-07-24

- Added a local heuristic malware scanner for mods: new Mod Security tab, scan mode (manual / on startup / after workshop download), warn-or-block policy, per-mod scan from the Mods tab context menu, and result caching keyed by mod content fingerprint.
- Block policy is enforced both at the enable checkbox and again at Apply time, so a mod flagged high risk after being selected can't slip through. It is a UI gate only: no files are touched, and already-active mods are never auto-disabled.
- Scan findings are fully visible: per-finding detail rows (rule, file, reason) in the Mod Security tab, tooltips on flagged status cells, and mod risk in the Mods table status column (HIGH RISK / SUSPICIOUS). Findings can be sent to the AI Assistant from the right-click menu.
- Tuned scanner severities: dynamic lua (`loadstring` / `loadfile` / `dofile`) warns instead of blocking since legit mods use it; only `os.execute` / `io.popen` / `package.loadlib` and executable file types are block-eligible. Filename checks use word boundaries so `generator.lua` no longer reads as "rat".
- Expanded the AI Assistant from 2 to 8 providers: Anthropic, OpenAI, Google Gemini, xAI Grok, DeepSeek, Mistral, OpenRouter, and local Ollama (no key required). Existing saved keys migrate automatically.
- Refreshed model lists to July 2026, all IDs verified against official sources (Claude Sonnet 5 / Opus 5, GPT-5.6, Gemini 3.6, DeepSeek V4, Grok 4.x); the model box stays editable for any custom ID.
- Added an integration test suite that exercises the OpenAI-compatible streaming path against a local mock server.

## v0.3 - 2026-05-02

- Updated AI Assistant model dropdowns and fresh-install defaults to reflect current OpenAI and Anthropic model names.
- Added an in-app Steam Workshop browser tab for Project Zomboid with Steam-only navigation, popout support, Steam client status, and quick rescan.
- Kept the embedded Workshop browser privacy-scoped: pzmm does not read, autofill, or persist Steam browser data.
- Opened Steam client protocol links externally so Workshop actions can hand off to the running Steam client.
