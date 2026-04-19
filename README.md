# pzmm | Project Zomboid Mod Manager

> Errors down to the Lua.

A standalone desktop mod manager for Project Zomboid B42. Scans your active mods, detects real runtime errors straight from `console.txt`, maps them back to the responsible mod, surfaces file conflicts, and solves load order. 

![Python](https://img.shields.io/badge/python-3.11+-blue) ![PyQt6](https://img.shields.io/badge/PyQt6-6.6+-green) ![PZ](https://img.shields.io/badge/Project%20Zomboid-B42-red)

---

**v0.2 being worked on currently!**

## Features

- **Error tracking** — parses `console.txt` and maps every Lua error and stack trace back to the mod that caused it. Only shows errors for mods you currently have active.
- **File conflict detection** — finds overlapping `.lua`, `.txt`, `.xml`, `.json`, and `.ini` files across mods and shows you which mod wins.
- **Load order solver** — topological sort based on mod dependencies, stable and deterministic across restarts. One-click apply writes the order back to disk.
- **Mod overview** — scans both Steam Workshop and local mod folders automatically, deduplicates versioned subfolders, reads your active mod list from the most recent save.
- **Dark UI** — native desktop app built with PyQt6, no browser required.

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

1. Launch the app
2. Click **Scan**
3. Check the **Errors** tab — mods ranked by error count, full stack traces on click
4. Check **Conflicts** to see which mods are fighting over the same files
5. Use **Load Order** → **Apply Order** to write a clean dependency-resolved order to disk

---

## Notes

- Patches to workshop mod files (e.g. B42 API fixes) will be overwritten when Steam updates those mods
- `console.txt` is from your last game session — rescan after launching the game with your current mod list for accurate results
- The **Apply Order** button writes to `modmanager-mods.txt` in your Zomboid folder

---

## License

MIT
