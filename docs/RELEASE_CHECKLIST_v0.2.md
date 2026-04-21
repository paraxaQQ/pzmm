# pzmm v0.2 Release Checklist

Use this as a hard gate before tagging `v0.2.0`.

## 1) Error Count Integrity
- [ ] On a known fixture log, `Errors` tab totals match parser totals.
- [ ] On your real `console.txt`, grouped issues + occurrence counts look sane.

## 2) No Hidden Errors
- [ ] Error groups include both runtime and engine-noise entries.
- [ ] Engine noise is labeled, not silently dropped.

## 3) Session Clarity
- [ ] Errors tab shows note that `console.txt` persists across sessions.
- [ ] Docs explain reproduce flow: launch -> reproduce -> rescan.

## 4) Attribution Confidence
- [ ] Each issue shows attribution (`direct` vs `inferred`).
- [ ] Inferred attribution is visually obvious in the Errors list.

## 5) Transactional Writes + Rollback
- [ ] Writing `modmanager-mods.txt` creates a timestamped backup when overwriting.
- [ ] New file creation path works (`VERSION=1` + mod line).
- [ ] Failures never leave a partial write (atomic temp replace).

## 6) Conflict Drill-Down
- [ ] Mods tab can jump to Conflicts tab for selected mod.
- [ ] First matching conflict is selected and detail panel updates.

## 7) Stress Pass
- [ ] Scan performance checked with large log + large mod list.
- [ ] UI remains responsive when switching tabs after scan.

## 8) Platform Scope
- [ ] Windows path flow verified end-to-end (Steam + local + Zomboid root).
- [ ] Non-Windows marked as best-effort for now.

## 9) Automated Test Gate
- [ ] `python -m unittest discover -s tests -p "test_*.py" -v` passes locally.
- [ ] GitHub Actions workflow green on the release commit.

## 10) Release Hygiene
- [ ] `CHANGELOG`/release notes mention new error counting behavior.
- [ ] Notes explain why v0.2 may report higher counts than v0.1.
- [ ] Rollback behavior for mod list writes is documented.

## Suggested Release Notes Bullets
- Accurate occurrence-based error counts (no more undercounting repeated failures).
- Engine wrapper/noise lines now visible and labeled separately.
- Error attribution now indicates direct vs inferred mapping.
- Safer mod list writes with automatic `.pzmm.bak-<timestamp>` backup.
- Mods tab shortcut to jump directly into matching file conflicts.

