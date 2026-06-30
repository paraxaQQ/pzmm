# pzmm v0.3 | Project Zomboid Mod Manager

**v0.4 soon?**

> Errors down to the Lua.

A standalone desktop mod manager for Project Zomboid B42. Scans your active mods, parses real runtime errors straight from `console.txt`, maps them back to the responsible mod, surfaces file conflicts, and handles load order. No guesswork.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![PyQt6](https://img.shields.io/badge/PyQt6-6.6+-green) ![PZ](https://img.shields.io/badge/Project%20Zomboid-B42-red)

---

## What it does

- **NEW!** **Built-in browser for PZ Steam Workshop!** - A built in browser tab under "Workshop" in the UI which allows you to sign-in to steam, browse, and install workshop mods all from 1 application! **pzmm does NOT save any cookies or sign-in credentials.**

- **Mod type detection** - tags mods by detected content such as maps, vehicles, weapons, items, clothing, recipes, tiles, textures, Lua, patches, dependencies, and more. Mods can have multiple tags, and the Mods tab can filter/search/sort by them.
- **Error tracking** — parses `console.txt` and maps every Lua error and stack trace back to the mod that caused it. Only shows errors from mods you currently have active. Tracks how many times each error has occurred, confidence level, cause chains, and whether attribution was direct or inferred.
- **Error diffing** — compare against everything in the current log, what changed since the last scan, or what changed since a baseline you set. Reset the baseline any time for cleaner regression tracking.
- **File conflict detection** — finds overlapping `.lua`, `.txt`, `.xml`, `.json`, and `.ini` files across mods, shows you which mod wins, and diffs the losing version against the winner so you can see exactly what's being overridden.
- **Load order solver** — topological sort based on mod dependencies, stable and deterministic across restarts. One-click apply writes the order back to disk with automatic timestamped backups.
- **Mod overview** — scans both Steam Workshop and local mod folders, deduplicates versioned subfolders, reads your active mod list from `modmanager-mods.txt`. Workshop vs local copies of the same mod show readable labels so you always know which is which.
- **Mod profiles** — save your current active mod list and load order as a named profile, then switch between them from a dialog. Useful for different playthroughs or testing setups.
- **Mod porting** — port mods between version folders directly in the app. Shows a dry-run preview before touching anything, with options to copy missing files or overwrite, optional pre-overwrite backup, and a manifest log for every port. Workshop mods can be cloned to a local copy first so you can work on them without touching the original.
- **AI Assistant** — chat with Claude or GPT about your mods using your own API key. Attach errors, mods, or files as context directly from right-click menus. Streaming responses, persistent chat history across sessions.
- **AI file editing with full rollback** — optionally let the AI read and patch mod files. Every write goes through a diff-confirmation dialog first, creates a timestamped backup, and is logged to a manifest. Roll back any single write or everything from the current session in one click.
- **Debug bundle export** — zips your console log, active mod info, and a summary report into one file for easy bug reports.
- **Color themes** — five built-in themes: Default, Gray, Red, Green, and Amber. Pick one from Settings and it previews live.
- **Native desktop UI** — built with PyQt6, no browser required.

---

## Requirements

- Python 3.11+
- Project Zomboid installed via Steam (Windows)

---

## Installation

```bash
git clone https://github.com/paraxaQQ/pzmm.git
cd pzmm
pip install -r requirements.txt
python main.py
```

### Standalone executable (no Python required)

```bash
pip install -r requirements-build.txt
python make_icon.py   # generates icon.ico (only needed once)
pyinstaller pzmm.spec
```

The built executable will be at `dist/pzmm.exe`.

---

## Usage

Launch the app, then hit **Scan**. The status bar walks through each step as it goes: detecting Steam libraries, loading mods, parsing conflicts, solving load order, and reading `console.txt`. When it finishes you'll see a summary like `Scan complete — 84 mods | 3 file conflicts | 12 errors | 2 warnings`.

If a new version is available, a pill appears in the toolbar. Click it to open the release page. No telemetry, no auto-download, and you can dismiss a specific version if you don't want to see it again.

### Overview tab

The first thing you see after a scan. Five stat cards at the top show your active mod count, error count, warnings, file conflicts, and dependency cycles, each color-coded by severity. Below that is a scrollable issues list covering your top errors, warnings, and conflicts. The **Export Debug Bundle** button at the top of that list zips your console log, all active mod.info files, and a summary report into one file — handy for attaching to bug reports or sharing with a mod author.

### Mods tab

A searchable table of every mod pzmm found, active or not. Check or uncheck mods to stage changes, then hit **Apply** to write them to disk. Pending changes show as `+X enable -Y disable` at the bottom, and **Undo** rolls them all back. Use the **Active only** checkbox to cut down the list.

The **Types** column shows the primary detected category first, with a compact `+N` count when supporting tags are present. A vehicle mod might show `Vehicles +6` instead of listing every bundled recipe, texture, translation, and Lua file in the table. By default, the type filter matches the displayed primary type only. Turn on **Include tags** to also match supporting tags, and use **Match all** to require every selected type/tag in that expanded mode. The search box also matches type names, and the table can be sorted by the Types column.

Selecting a mod shows a details strip below the table with its detected types, ID, source, PZ version, workshop ID, dependencies, and folder path.

Right-clicking any mod row gives you:

- **Open mod folder** and **open mod.info in editor** (auto-detects Notepad++ or falls back to Notepad)
- **View file conflicts** — jumps to the Conflicts tab filtered to that mod
- **Port Version Folder** (local mods) or **Clone To Local + Port** (workshop mods) — see the porting section below
- AI actions if the assistant is enabled

### Conflicts tab

The left panel lists every file where two or more mods overlap. Click any conflict to see the full breakdown on the right: which mod wins, which mods are overridden, whether the content is actually different or just byte-identical, and a unified diff of the losing version against the winner.

### Load Order tab

Shows the topologically-sorted load order on the left and the full dependency edge list on the right. If there are circular dependencies they show up in red at the top of the right panel. Hit **Apply Order** to write the suggested order to disk.

### Errors tab

Select a mod on the left to see all of its errors on the right. The detail tree shows each error's severity, confidence, file, line number, cause chain, and an explanation of why it matters. Click an error to see the full stack trace text at the bottom.

Use the **diff mode** dropdown to change what you're looking at:

- **Everything in current log** — all errors in the current console.txt
- **Changed since previous scan** — only what's new or increased since the last time you scanned
- **Changed since baseline** — errors that appeared after you set the baseline, useful for isolating regressions

Hit **Reset baseline** to mark the current state as your new reference point. The **How to read errors** button opens an in-app guide explaining the columns.

If the AI is enabled, **Send diff to AI** attaches the current error diff to the AI tab as context.

### Profiles

Click **Profiles** in the toolbar to open the profiles dialog. Hit **Save current as** to snapshot your active mod list and load order under a name. From the table you can load a profile (writes to `modmanager-mods.txt` and rescans), overwrite a profile with your current setup, or delete it. Profiles are stored in `%APPDATA%/pzmm/profiles/`.

### Mod porting

Right-click a local mod and choose **Port Version Folder** to copy files from one version folder to another within the same mod. The dialog shows all detected version folders, lets you pick source and target, and shows a preview of what will be copied before anything happens.

For workshop mods, **Clone To Local + Port** first copies the entire workshop mod to your local mods directory, then opens the porting dialog on the clone. After porting you'll be offered the option to export a workshop-ready copy with `.pzmm` artifacts stripped out. The mod list rescans automatically after cloning or porting.

---

## AI Assistant

The AI tab is hidden until you enable it in Settings.

### Setup

1. Click the gear icon in the top-right to open Settings
2. Toggle **Enable AI Assistant** on
3. Pick a provider — **Anthropic (Claude)** or **OpenAI (GPT)**
4. Paste your API key, pick a model, and optionally write a custom system prompt
5. Hit **Save**

Keys are stored locally in `%APPDATA%/pzmm/config.json` and only ever leave your machine to reach the provider you selected.

### Chatting

Open the **AI Assistant** tab and type in the input box. You can start fresh conversations with the **New chat** button, and switch between past conversations with the dropdown at the top. The app saves up to 30 recent conversations.

For context-aware questions, use the right-click menus rather than copy-pasting:

- In the **Mods** tab: right-click any mod and choose **Ask AI about this mod** (attaches mod.info) or **Debug this mod with AI** (attaches mod.info, errors, and key Lua files)
- In the **Errors** tab: right-click any error and choose **Ask AI about this error** (attaches the error and optionally the source `.lua` file)

Attachments appear as chips above the input box and can be removed individually before sending.

### File access and safety

By default the AI can only read files. To let it write, enable **Allow file access** in Settings under the File Access and Safety section. File access is locked out until the AI is enabled.

When file access is on, every write the AI attempts:

- Shows a unified diff and waits for your confirmation (turn on **Trusted mode** to skip this)
- Creates a `.pzmm.bak-<timestamp>` backup next to the original file
- Is logged to `%APPDATA%/pzmm/backups.json`

Open **History and Revert** in the AI tab at any time to see a list of every write the AI has made and roll back any of them individually or all at once.

**Protect game data** is on by default and blocks writes under `Saves`, `Sandbox Presets`, and `ActiveMods` paths even when file access is enabled.

---

## Notes

- Workshop mod patches will be overwritten when Steam updates those mods
- `console.txt` accumulates across sessions. For clean results, launch PZ, reproduce your issue, quit, then rescan
- If you enable **Watch console.txt** in Settings, the Errors tab updates live while the game is running

---

## License

MIT

---

## Developer

Run unit tests locally:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
