# Mod Version Porting Plan (v0.25 Candidate)

## Why this matters

Many PZ mods ship versioned subfolders (`42`, `42.13`, `42.16`, etc). Porting manually is slow and error-prone when users need to test a newer game build quickly.

## Findings from real data

- Workshop mods scanned: `325`
- Mods with versioned subfolders: `236`
- This is common enough to justify first-class tooling.

## Scope for first release (safe + useful)

1. Local mods only
- Add a **Port Version Folder...** action in the Mods tab (for `source=local`).
- Select `from_version` -> `to_version`.
- Copy tree recursively (`from` to `to`) with overwrite prompt.
- Write a manifest of copied files and created directories for rollback.

2. Read-only workshop support (phase 2)
- Detect workshop versioned layouts and offer:
  - **Clone to local mod** (new local workspace), then port there.
- Avoid writing directly inside workshop content (Steam update risk).

3. Guardrails
- Refuse destructive operations outside target mod folder.
- Dry-run preview: show file counts + changed paths before execute.
- Auto-backup target version folder when it already exists.

## UX draft

- Context menu (Mods tab):
  - `Port Version Folder...`
- Dialog:
  - Source version dropdown
  - Target version input/dropdown
  - Options:
    - `Copy only missing files`
    - `Overwrite existing files`
    - `Create backup before overwrite`
  - Preview list (`N files copied`, `M overwritten`)

## Future enhancements

- Heuristic patching for known B41 -> B42 API changes.
- Conflict-aware merge for `.lua`/`.txt` instead of pure copy.
- One-click rollback for last port operation.
