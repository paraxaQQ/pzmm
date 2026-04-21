# How To Read Errors

This panel is meant to help you triage quickly, even if you are new to PZ modding.

## What each row means

- `Severity`
  - `ERROR`: something failed and can break behavior.
  - `WARN`: suspicious, but may still run.
  - `NOISE`: engine/log spam around errors (still useful context).
- `Message / Stack`: short summary of what happened.
- `Cause`: exception chain, usually wrapper -> root cause.
- `File` + `Line`: best-known location from the log.

## Why some items say `[inferred]`

- `direct`: log line names the mod directly.
- `inferred`: parser linked the line to the most recent mod context.
- `unattributed`: severity line was kept, but could not be tied to a specific mod.
- Inferred lines are still useful, but treat them as lower confidence.

## What to fix first

1. High-occurrence errors (`x###`) from active mods.
2. Errors with a clear root cause in `Cause` (for example `IllegalStateException: ...`).
3. Conflicts that touch the same file as the failing script.
4. Warnings after the main errors are addressed.

## Fast triage workflow

1. Open the mod in `Errors` and sort by repeated failures.
2. Click the top error and read `Cause chain`.
3. Right-click -> `Ask AI about this error + source file`.
4. Check `Conflicts` for that mod if file overlap exists.
5. Disable only the suspect mod(s), rescan, and compare.

## Common patterns

- `...Exception thrown` + `Cause: IllegalStateException/RuntimeException`
  - Usually a real mod bug in Lua logic or assumptions.
- `KahluaThread.flushErrorMessage > dumping Lua stack trace`
  - Usually noise emitted after a real error. Keep for context, do not treat as root cause by itself.
- `no such function ...`
  - Missing API, load order issue, or game/version mismatch.

## Important note about console.txt

Project Zomboid appends logs across sessions. Old failures can still show up.

For current-run-only diagnostics:

1. Launch game.
2. Reproduce issue.
3. Rescan immediately.
