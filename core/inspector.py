"""Console log parser — maps real runtime errors back to mods."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModError:
    mod_id: str
    mod_name: str
    severity: str        # "error" | "warn"
    message: str
    file: str
    line: int
    stack: list[str] = field(default_factory=list)


@dataclass
class ConsoleReport:
    errors: list[ModError] = field(default_factory=list)
    warns:  list[ModError] = field(default_factory=list)

    @property
    def by_mod(self) -> dict[str, list[ModError]]:
        out: dict[str, list[ModError]] = {}
        for e in self.errors + self.warns:
            out.setdefault(e.mod_id, []).append(e)
        return out


# Matches:  ERROR: General ... > Lua((MOD:Spongie's Clothing)).foo> Exception thrown
_RE_LUA_MOD  = re.compile(r'Lua\(\(MOD:([^)]+)\)\)\.([^\s>]+)')
# Matches:  WARN : Lua ... > Lua((MOD:Foo)).bar > require("x") failed
_RE_WARN_MOD = re.compile(r'Lua\(\(MOD:([^)]+)\)\)[.\w]*>\s*require\("([^"]+)"\) failed')
# Matches:  at SomeFile.lua:12
_RE_STACK    = re.compile(r'at\s+([\w./\\]+\.lua):(\d+)')
# Matches severity prefix
_RE_SEV      = re.compile(r'^(ERROR|SEVERE|WARN)\s*[:\s]')


def parse_console(console_path: Path, mod_name_map: dict[str, str]) -> ConsoleReport:
    """
    mod_name_map: mod_id → display name (best effort, falls back to raw name from log)
    """
    report = ConsoleReport()
    if not console_path.exists():
        return report

    try:
        lines = console_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return report

    i = 0
    while i < len(lines):
        raw = lines[i]

        sev_m = _RE_SEV.match(raw)
        if not sev_m:
            i += 1
            continue

        sev = sev_m.group(1)
        severity = "error" if sev in ("ERROR", "SEVERE") else "warn"

        # ── Lua mod error ─────────────────────────────────────────────────────
        lua_m = _RE_LUA_MOD.search(raw)
        if lua_m:
            raw_name = lua_m.group(1).strip()
            lua_file = lua_m.group(2).strip()

            # Collect message (rest of line after last >)
            msg_part = raw.split(">")[-1].strip()

            # Collect stack trace lines that follow
            stack: list[str] = []
            j = i + 1
            while j < len(lines) and j < i + 20:
                sl = lines[j].strip()
                if sl.startswith("Lua(") or _RE_SEV.match(lines[j]):
                    break
                if sl and not sl.startswith("---"):
                    stack.append(sl)
                j += 1

            # Best guess at line number from stack
            lineno = 0
            for s in stack:
                nm = _RE_STACK.search(s)
                if nm:
                    lineno = int(nm.group(2))
                    break

            # Deduplicate: skip if we already have same mod+msg combo
            existing = report.errors if severity == "error" else report.warns
            dup = any(
                e.mod_name == raw_name and e.message == msg_part
                for e in existing
            )
            if not dup:
                mod_id = raw_name.lower().replace(" ", "").replace("'", "")
                entry = ModError(
                    mod_id=mod_id,
                    mod_name=raw_name,
                    severity=severity,
                    message=msg_part,
                    file=lua_file,
                    line=lineno,
                    stack=stack[:8],
                )
                existing.append(entry)
            i = j
            continue

        # ── require() failed warning ──────────────────────────────────────────
        if severity == "warn":
            warn_m = _RE_WARN_MOD.search(raw)
            if warn_m:
                raw_name = warn_m.group(1).strip()
                req_path = warn_m.group(2).strip()
                mod_id   = raw_name.lower().replace(" ", "").replace("'", "")
                dup = any(
                    e.mod_name == raw_name and e.file == req_path
                    for e in report.warns
                )
                if not dup:
                    report.warns.append(ModError(
                        mod_id=mod_id,
                        mod_name=raw_name,
                        severity="warn",
                        message=f'require("{req_path}") failed',
                        file=req_path,
                        line=0,
                    ))

        i += 1

    return report


def run_inspection(mods, console_path: Path | None = None):
    """Returns (report, func_conflicts=[]) — kept for API compat with app.py."""
    name_map = {m.id: m.name for m in mods}
    if console_path and console_path.exists():
        report = parse_console(console_path, name_map)
    else:
        report = ConsoleReport()

    # Filter to only currently-active mods — console.txt persists across
    # sessions so removed mods would still appear otherwise.
    if mods:
        _norm = lambda s: s.lower().replace(" ", "").replace("'", "").replace("-", "")
        active = {_norm(m.name) for m in mods} | {_norm(m.id) for m in mods}
        report.errors = [e for e in report.errors if _norm(e.mod_name) in active]
        report.warns  = [e for e in report.warns  if _norm(e.mod_name) in active]

    return report, []
