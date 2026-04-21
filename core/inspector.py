"""Console log parser — maps runtime errors/warnings back to mods when possible."""
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
    occurrence_count: int = 1
    kind: str = "runtime"  # runtime | lua_runtime | require_failed | engine_noise
    attribution: str = "direct"  # direct | inferred
    confidence: str = "high"  # high | medium | low
    attribution_reason: str = ""
    candidate_mods: list[str] = field(default_factory=list)
    cause_chain: str = ""


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

    @property
    def error_occurrences(self) -> int:
        return sum(max(1, e.occurrence_count) for e in self.errors)

    @property
    def warn_occurrences(self) -> int:
        return sum(max(1, e.occurrence_count) for e in self.warns)


# Matches:  ERROR: ... > Lua((MOD:Spongie's Clothing)).foo > Exception thrown
_RE_LUA_MOD  = re.compile(r'Lua\(\(MOD:([^)]+)\)\)\.([^\s>]+)')
# Any Lua((MOD:...)) marker in nearby context.
_RE_MOD_ANY  = re.compile(r'Lua\(\(MOD:([^)]+)\)\)')
# Matches:  WARN : ... > Lua((MOD:Foo)).bar > require("x") failed
_RE_WARN_MOD = re.compile(r'Lua\(\(MOD:([^)]+)\)\)[.\w]*>\s*require\("([^"]+)"\) failed')
# Matches:  at SomeFile.lua:12
_RE_STACK    = re.compile(r'at\s+([\w./\\-]+\.lua):(\d+)', re.IGNORECASE)
# Matches: function: foo -- file: media/lua/client/X.lua line #123
_RE_FILELINE = re.compile(r'file:\s*([^\s,]+\.lua)(?:\s+line\s*[#:]?\s*(\d+))?', re.IGNORECASE)
# Matches: [string "media/lua/client/X.lua"]:123
_RE_STRLINE  = re.compile(r'\[string\s+"([^"]+\.lua)"\]\s*[:)]\s*(\d+)', re.IGNORECASE)
# Matches quoted file hints in generic script/runtime lines.
_RE_QUOTED_PATH = re.compile(
    r"""['"]([^'"]+\.(?:lua|txt|xml|json|ini|cfg|bin))['"]""",
    re.IGNORECASE,
)
# Matches unquoted file hints, including paths with spaces (e.g. maps/.../objects.lua).
_RE_PATH_HINT = re.compile(
    r"""((?:media|maps|lua|scripts)[\\/][^>\r\n]*?\.(?:lua|txt|xml|json|ini|cfg|bin))""",
    re.IGNORECASE,
)
# Matches severity prefix (tolerates leading whitespace + WARN :)
_RE_SEV      = re.compile(r'^\s*(ERROR|SEVERE|WARN)\s*[:\s]', re.IGNORECASE)
_RE_CAUSED_BY = re.compile(r'caused by:\s*(.+)', re.IGNORECASE)
_RE_EXCEPTION_LINE = re.compile(r'([\w.$]+(?:Exception|Error)):\s*(.+)')
_RE_EXCEPTION_TOKEN = re.compile(r'^([\w.$]+(?:Exception|Error))(?::\s*(.+)|\s+at\b.*)?$')
_RE_NO_SUCH_FUNCTION = re.compile(r'no such function\s+"([^"]+)"', re.IGNORECASE)
_RE_NEEDED_BY = re.compile(r'needed by\s+([A-Za-z0-9_ \-\[\]\'"]+)\s+not found', re.IGNORECASE)
_RE_VEHICLE_MSG = re.compile(r'vehicle\s+"([^"]+)"', re.IGNORECASE)
_RE_VEHICLE_DEF = re.compile(r'^\s*vehicle\s+([A-Za-z0-9_.-]+)\b', re.IGNORECASE | re.MULTILINE)
_RE_CREATE_SYMBOL = re.compile(r'\bcreate\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\b', re.IGNORECASE)
_RE_FUNC_SYMBOL = re.compile(r'\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\b')
_RE_ASSIGN_FUNC_SYMBOL = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*function\b', re.IGNORECASE)

_ENGINE_NOISE_MARKERS = (
    "kahluathread.flusherrormessage",
    "dumping lua stack trace",
)
_UNATTRIBUTED_ID = "__unattributed__"
_UNATTRIBUTED_NAME = "Unattributed / Engine"
_RE_VERSION_DIR = re.compile(r'^\d+(?:\.\d+)*$')

def _norm_mod_key(s: str) -> str:
    return s.lower().replace(" ", "").replace("'", "").replace("-", "")


def _build_mod_lookup(mod_name_map: dict[str, str]) -> dict[str, tuple[str, str]]:
    """
    Build a normalized lookup:
      token -> (normalized_mod_id, display_name)
    """
    out: dict[str, tuple[str, str]] = {}
    for mid, name in mod_name_map.items():
        mid_n = _norm_mod_key(mid)
        name_n = _norm_mod_key(name)
        out[mid_n] = (mid_n, name or mid)
        if name_n:
            out.setdefault(name_n, (mid_n, name or mid))
    return out


def _resolve_mod(raw_name: str, lookup: dict[str, tuple[str, str]]) -> tuple[str, str]:
    token = _norm_mod_key(raw_name)
    if token in lookup:
        return lookup[token]
    return token, raw_name.strip() or raw_name


def _strip_severity_prefix(raw: str) -> str:
    return _RE_SEV.sub("", raw, count=1).strip()


def _looks_stack_like(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    l = s.lower()
    return (
        "stack traceback" in l
        or l.startswith("function:")
        or l.startswith("at ")
        or l.startswith("lua stack")
        or l.startswith("[string ")
        or " file: " in l
        or ".lua" in l
    )


def _collect_pre_stack(lines: list[str], idx: int,
                       *, lookback: int = 25, limit: int = 8) -> list[str]:
    """
    PZ often emits stack lines immediately BEFORE an ERROR/WARN line.
    Grab a contiguous block above, but only if the block looks stack-like.
    """
    block: list[str] = []
    j = idx - 1
    while j >= 0 and (idx - j) <= lookback and len(block) < limit:
        raw = lines[j]
        if _RE_SEV.match(raw):
            break
        s = raw.strip()
        if not s:
            if block:
                break
            j -= 1
            continue
        block.append(s)
        j -= 1

    block.reverse()
    if not any(_looks_stack_like(x) for x in block):
        return []
    return block


def _collect_post_stack(lines: list[str], idx: int,
                        *, lookahead: int = 25, limit: int = 8) -> list[str]:
    out: list[str] = []
    j = idx + 1
    started = False

    while j < len(lines) and (j - idx) <= lookahead and len(out) < limit:
        raw = lines[j]
        if _RE_SEV.match(raw):
            break

        s = raw.strip()
        if not s:
            if started:
                break
            j += 1
            continue

        if _looks_stack_like(s):
            started = True
            out.append(s)
        elif started:
            # Keep short continuation lines once stack capture has started.
            out.append(s)

        j += 1

    return out


def _merge_stack(pre: list[str], post: list[str], limit: int = 8) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for s in pre + post:
        if s in seen:
            continue
        seen.add(s)
        merged.append(s)
        if len(merged) >= limit:
            break
    return merged


def _extract_file_line(texts: list[str]) -> tuple[str, int]:
    def _clean_path_hint(path: str) -> str:
        return path.strip().rstrip(".,:;)]}").replace("\\", "/")

    for s in texts:
        m = _RE_STACK.search(s)
        if m:
            return m.group(1), int(m.group(2))

        m = _RE_FILELINE.search(s)
        if m:
            return m.group(1), int(m.group(2)) if m.group(2) else 0

        m = _RE_STRLINE.search(s)
        if m:
            return m.group(1), int(m.group(2))

        m = _RE_QUOTED_PATH.search(s)
        if m:
            return _clean_path_hint(m.group(1)), 0

        m = _RE_PATH_HINT.search(s)
        if m:
            return _clean_path_hint(m.group(1)), 0

    return "", 0


def _extract_message(raw: str, *, lua_mode: bool = False) -> str:
    # For Lua((MOD:...)) entries, the actionable bit is usually the last segment.
    if lua_mode and ">" in raw:
        msg = raw.split(">")[-1].strip()
        if msg:
            return msg

    body = _strip_severity_prefix(raw)
    if ">" in body:
        parts = [p.strip() for p in body.split(">") if p.strip()]
        if len(parts) >= 2:
            # Keep one level of context + tail message.
            return " > ".join(parts[-2:])
        if parts:
            return parts[-1]

    return body


def _looks_mod_related_message(msg: str) -> bool:
    """
    Generic severity lines we can reasonably treat as Lua/mod runtime failures
    when they appear near an attributed mod context.
    """
    m = msg.lower()
    return (
        "luamanager.getfunctionobject" in m
        or "no such function" in m
        or "exception thrown" in m
        or "runtimeexception" in m
        or "illegalstateexception" in m
        or "lua" in m
    )


def _is_engine_noise_message(msg: str) -> bool:
    m = msg.lower()
    return any(marker in m for marker in _ENGINE_NOISE_MARKERS)


def _collect_cause_line(lines: list[str], idx: int, *, lookahead: int = 20) -> str:
    j = idx + 1
    while j < len(lines) and (j - idx) <= lookahead:
        raw = lines[j]
        if _RE_SEV.match(raw):
            break
        s = raw.strip()
        if not s:
            j += 1
            continue

        caused = _RE_CAUSED_BY.search(s)
        if caused:
            return caused.group(1).strip()

        exc = _RE_EXCEPTION_LINE.search(s)
        if exc:
            return f"{exc.group(1)}: {exc.group(2).strip()}"

        j += 1
    return ""


def _normalize_exception_token(text: str) -> str:
    s = text.strip()
    if not s:
        return ""

    caused = _RE_CAUSED_BY.search(s)
    if caused:
        s = caused.group(1).strip()

    m = _RE_EXCEPTION_LINE.search(s)
    if m:
        return f"{m.group(1)}: {m.group(2).strip()}"

    m = _RE_EXCEPTION_TOKEN.search(s)
    if m:
        cls = m.group(1)
        msg = (m.group(2) or "").strip()
        return f"{cls}: {msg}" if msg else cls

    return ""


def _merge_cause_chain(existing: str, incoming: str) -> str:
    if not existing:
        return incoming
    if not incoming:
        return existing

    merged: list[str] = []
    seen: set[str] = set()
    for chain in (existing, incoming):
        for part in [p.strip() for p in chain.split("->") if p.strip()]:
            if part in seen:
                continue
            seen.add(part)
            merged.append(part)
    return " -> ".join(merged)


def _collect_cause_chain(
    lines: list[str],
    idx: int,
    raw: str,
    stack: list[str],
    *,
    lookahead: int = 30,
    limit: int = 6,
) -> str:
    candidates: list[str] = [raw]

    j = idx + 1
    while j < len(lines) and (j - idx) <= lookahead:
        nxt = lines[j]
        if _RE_SEV.match(nxt):
            break
        s = nxt.strip()
        if s:
            candidates.append(s)
        j += 1

    # Stack lines sometimes include exception wrappers too.
    candidates.extend(stack[:8])

    parts: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        token = _normalize_exception_token(c)
        if not token or token in seen:
            continue
        seen.add(token)
        parts.append(token)
        if len(parts) >= limit:
            break

    return " -> ".join(parts)


def _upsert_issue(
    target: list[ModError],
    *,
    mod_id: str,
    mod_name: str,
    severity: str,
    message: str,
    file: str,
    line: int,
    stack: list[str],
    kind: str = "runtime",
    attribution: str = "direct",
    confidence: str = "high",
    attribution_reason: str = "",
    candidate_mods: list[str] | None = None,
    cause_chain: str = "",
) -> None:
    candidate_mods = list(candidate_mods or [])
    conf_rank = {"low": 0, "medium": 1, "high": 2}

    for e in target:
        if (
            e.mod_id == mod_id
            and e.message == message
            and e.file == file
            and e.line == line
            and e.kind == kind
        ):
            e.occurrence_count += 1
            if e.attribution != "direct" and attribution == "direct":
                e.attribution = "direct"
            if conf_rank.get(confidence, 0) > conf_rank.get(e.confidence, 0):
                e.confidence = confidence
            if attribution_reason:
                if not e.attribution_reason:
                    e.attribution_reason = attribution_reason
                elif attribution_reason not in e.attribution_reason:
                    e.attribution_reason = f"{e.attribution_reason}; {attribution_reason}"
            if candidate_mods:
                existing = {x for x in e.candidate_mods}
                for c in candidate_mods:
                    if c not in existing:
                        e.candidate_mods.append(c)
                        existing.add(c)
                        if len(e.candidate_mods) >= 6:
                            break
            if cause_chain:
                e.cause_chain = _merge_cause_chain(e.cause_chain, cause_chain)
            if stack:
                for s in stack[:8]:
                    if s not in e.stack:
                        e.stack.append(s)
                        if len(e.stack) >= 8:
                            break
            return

    target.append(ModError(
        mod_id=mod_id,
        mod_name=mod_name,
        severity=severity,
        message=message,
        file=file,
        line=line,
        stack=stack[:8],
        occurrence_count=1,
        kind=kind,
        attribution=attribution,
        confidence=confidence,
        attribution_reason=attribution_reason,
        candidate_mods=candidate_mods[:6],
        cause_chain=cause_chain,
    ))


def _candidate_from_mod_obj(mod) -> tuple[str, str]:
    mid = _norm_mod_key(getattr(mod, "id", "") or "")
    name = (getattr(mod, "name", "") or getattr(mod, "id", "") or "").strip()
    return mid, name or mid


def _iter_media_roots(mod, leaf: str) -> list[Path]:
    """
    Return plausible media roots for mods that use:
      - root/media/<leaf>
      - root/common/media/<leaf>
      - root/<version>/media/<leaf>
      - root/<version>/common/media/<leaf>
    """
    roots: list[Path] = []
    base = getattr(mod, "path", Path("."))
    roots.append(base / "media" / leaf)
    roots.append(base / "common" / "media" / leaf)
    # Some mods keep versioned content in <mod>/<ver>/... and shared assets
    # in sibling <mod>/common/...
    if _RE_VERSION_DIR.match(base.name):
        roots.append(base.parent / "media" / leaf)
        roots.append(base.parent / "common" / "media" / leaf)

    try:
        for child in base.iterdir():
            if not child.is_dir() or not _RE_VERSION_DIR.match(child.name):
                continue
            roots.append(child / "media" / leaf)
            roots.append(child / "common" / "media" / leaf)
    except Exception:
        pass

    uniq: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        key = str(r).lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq


def _path_exists_casefold(base: Path, rel_file: str) -> bool:
    cur = base
    parts = [p for p in rel_file.replace("\\", "/").split("/") if p and p != "."]
    if not parts:
        return False

    for part in parts:
        try:
            lower = part.lower()
            nxt = None
            for child in cur.iterdir():
                if child.name.lower() == lower:
                    nxt = child
                    break
            if nxt is None:
                return False
            cur = nxt
        except Exception:
            return False
    return cur.exists()


def _build_symbol_mod_index(mods) -> dict[str, set[tuple[str, str]]]:
    """
    Build symbol -> candidate mods map from:
      - script hooks: create = SYMBOL
      - lua defs: function SYMBOL
      - lua defs: SYMBOL = function(...)
    """
    out: dict[str, set[tuple[str, str]]] = {}
    for mod in mods:
        ident = _candidate_from_mod_obj(mod)
        for roots, exts in (
            (_iter_media_roots(mod, "scripts"), {".txt"}),
            (_iter_media_roots(mod, "lua"), {".lua"}),
        ):
            for base in roots:
                if not base.exists():
                    continue
                for f in base.rglob("*"):
                    if not f.is_file() or f.suffix.lower() not in exts:
                        continue
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue

                    if ".txt" in exts:
                        for m in _RE_CREATE_SYMBOL.finditer(text):
                            sym = m.group(1).strip().lower()
                            if sym:
                                out.setdefault(sym, set()).add(ident)

                    if ".lua" in exts:
                        for pat in (_RE_FUNC_SYMBOL, _RE_ASSIGN_FUNC_SYMBOL):
                            for m in pat.finditer(text):
                                sym = m.group(1).strip().lower()
                                if sym:
                                    out.setdefault(sym, set()).add(ident)

    return out


def _build_vehicle_mod_index(mods) -> dict[str, set[tuple[str, str]]]:
    out: dict[str, set[tuple[str, str]]] = {}
    for mod in mods:
        ident = _candidate_from_mod_obj(mod)
        for base in _iter_media_roots(mod, "scripts"):
            if not base.exists():
                continue
            for f in base.rglob("*.txt"):
                if not f.is_file():
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for m in _RE_VEHICLE_DEF.finditer(text):
                    vid = m.group(1).strip().lower()
                    if vid:
                        out.setdefault(vid, set()).add(ident)
    return out


def _mod_candidates_from_file(mods, rel_file: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    rf = rel_file.strip().replace("\\", "/").lstrip("./")
    if not rf:
        return out

    for mod in mods:
        base = getattr(mod, "path", Path("."))
        candidates = [base]
        candidates.append(base / "common")
        if _RE_VERSION_DIR.match(base.name):
            candidates.append(base.parent)
            candidates.append(base.parent / "common")
        try:
            for child in base.iterdir():
                if child.is_dir() and _RE_VERSION_DIR.match(child.name):
                    candidates.append(child)
                    candidates.append(child / "common")
        except Exception:
            pass
        for c in candidates:
            if _path_exists_casefold(c, rf):
                out.add(_candidate_from_mod_obj(mod))
                break
    return out


def _reattribute_unattributed(report: ConsoleReport, mods, mod_name_map: dict[str, str]) -> None:
    """
    Best-effort second pass that moves some "__unattributed__" lines to a
    concrete mod when there is a single confident candidate.
    """
    mod_lookup = _build_mod_lookup(mod_name_map)
    symbol_index: dict[str, set[tuple[str, str]]] | None = None
    vehicle_index: dict[str, set[tuple[str, str]]] | None = None

    entries = report.errors + report.warns
    for e in entries:
        if e.mod_id != _UNATTRIBUTED_ID:
            continue

        candidates: dict[tuple[str, str], set[str]] = {}

        def _add_candidates(found: set[tuple[str, str]], reason: str):
            for cand in found:
                candidates.setdefault(cand, set()).add(reason)

        def _reason_text(tags: set[str]) -> str:
            ordered = []
            mapping = {
                "needed_by": "matched 'needed by <mod>' marker",
                "file_hint": "matched file path ownership",
                "symbol": "matched missing function symbol index",
                "vehicle": "matched vehicle id index",
            }
            for key in ("needed_by", "file_hint", "symbol", "vehicle"):
                if key in tags:
                    ordered.append(mapping[key])
            return ", ".join(ordered)

        # 1) "needed by <mod>" style hints
        needed = _RE_NEEDED_BY.search(e.message or "")
        if needed:
            raw = needed.group(1).strip().strip("'\"")
            mid, mname = _resolve_mod(raw, mod_lookup)
            if mid and mname:
                _add_candidates({(mid, mname)}, "needed_by")

        # 2) explicit file hints
        if e.file:
            _add_candidates(_mod_candidates_from_file(mods, e.file), "file_hint")

        # 3) no-such-function symbols
        miss = _RE_NO_SUCH_FUNCTION.search(e.message or "")
        if miss:
            symbol = miss.group(1).strip().lower()
            if symbol:
                if symbol_index is None:
                    symbol_index = _build_symbol_mod_index(mods)
                _add_candidates(symbol_index.get(symbol, set()), "symbol")

        # 4) vehicle id hints
        vm = _RE_VEHICLE_MSG.search(e.message or "")
        if vm:
            vid = vm.group(1).strip().lower()
            if vid:
                if vehicle_index is None:
                    vehicle_index = _build_vehicle_mod_index(mods)
                _add_candidates(vehicle_index.get(vid, set()), "vehicle")

        if len(candidates) == 1:
            (mid, mname), why_tags = next(iter(candidates.items()))
            e.mod_id = mid
            e.mod_name = mname
            e.attribution = "inferred"
            e.confidence = "high" if ({"needed_by", "file_hint"} & why_tags) else "medium"
            e.attribution_reason = _reason_text(why_tags) or "inferred from indexed evidence"
            e.candidate_mods = []
        elif len(candidates) > 1:
            e.attribution = "unattributed"
            e.confidence = "low"
            e.attribution_reason = "multiple possible mods matched indexed evidence"
            e.candidate_mods = sorted({name for _, name in candidates.keys()})[:6]


def parse_console(console_path: Path, mod_name_map: dict[str, str]) -> ConsoleReport:
    """
    mod_name_map: mod_id -> display name (best effort matching for attribution)
    """
    report = ConsoleReport()
    if not console_path.exists():
        return report

    try:
        lines = console_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return report

    mod_lookup = _build_mod_lookup(mod_name_map)
    last_mod_context: tuple[str, str] | None = None
    last_mod_line = -10_000

    i = 0
    while i < len(lines):
        raw = lines[i]

        sev_m = _RE_SEV.match(raw)
        if not sev_m:
            i += 1
            continue

        severity = "error" if sev_m.group(1).upper() in ("ERROR", "SEVERE") else "warn"
        pre_stack = _collect_pre_stack(lines, i)
        post_stack = _collect_post_stack(lines, i)
        stack = _merge_stack(pre_stack, post_stack, limit=8)
        cause_chain = _collect_cause_chain(lines, i, raw, stack)

        # -- Lua-attributed error/warn
        lua_m = _RE_LUA_MOD.search(raw)
        if lua_m:
            raw_name = lua_m.group(1).strip()
            lua_file = lua_m.group(2).strip()
            msg_part = _extract_message(raw, lua_mode=True)
            if msg_part.lower() == "exception thrown":
                cause = _collect_cause_line(lines, i)
                if cause:
                    msg_part = f"Exception thrown: {cause}"
            stack_file, stack_line = _extract_file_line(stack)

            existing = report.errors if severity == "error" else report.warns
            mod_id, mod_name = _resolve_mod(raw_name, mod_lookup)
            _upsert_issue(
                existing,
                mod_id=mod_id,
                mod_name=mod_name,
                severity=severity,
                message=msg_part,
                file=lua_file or stack_file,
                line=stack_line,
                stack=stack,
                kind="lua_runtime",
                attribution="direct",
                confidence="high",
                attribution_reason="Matched explicit Lua((MOD:...)) marker in log line.",
                cause_chain=cause_chain,
            )
            last_mod_context = (mod_id, mod_name)
            last_mod_line = i
            i += 1
            continue

        # -- require() warning shape
        if severity == "warn":
            warn_m = _RE_WARN_MOD.search(raw)
            if warn_m:
                raw_name = warn_m.group(1).strip()
                req_path = warn_m.group(2).strip()
                mod_id, mod_name = _resolve_mod(raw_name, mod_lookup)
                _upsert_issue(
                    report.warns,
                    mod_id=mod_id,
                    mod_name=mod_name,
                    severity="warn",
                    message=f'require("{req_path}") failed',
                    file=req_path,
                    line=0,
                    stack=stack,
                    kind="require_failed",
                    attribution="direct",
                    confidence="high",
                    attribution_reason="Matched explicit Lua((MOD:...)) require() failure marker.",
                    cause_chain=cause_chain,
                )
                last_mod_context = (mod_id, mod_name)
                last_mod_line = i
                i += 1
                continue

        # -- Generic fallback, but MOD-FOCUSED:
        #    only keep the line if we can attribute it to a mod marker
        #    directly, or infer it from very recent mod context.
        msg = _extract_message(raw)
        if msg:
            raw_mod_name = ""
            mod_hit = _RE_MOD_ANY.search(raw)
            if mod_hit:
                raw_mod_name = mod_hit.group(1).strip()
            else:
                for s in stack:
                    m = _RE_MOD_ANY.search(s)
                    if m:
                        raw_mod_name = m.group(1).strip()
                        break

            if raw_mod_name:
                mod_id, mod_name = _resolve_mod(raw_mod_name, mod_lookup)
                last_mod_context = (mod_id, mod_name)
                last_mod_line = i
                attribution = "direct"
            else:
                can_use_context = (
                    last_mod_context is not None
                    and (i - last_mod_line) <= 40
                    and _looks_mod_related_message(msg)
                )
                if can_use_context:
                    mod_id, mod_name = last_mod_context
                    attribution = "inferred"
                    confidence = "medium"
                    why = "No direct marker; inferred from recent mod context and Lua-related signature."
                else:
                    # Keep all severity lines, even when we cannot confidently
                    # tie them to a specific mod.
                    mod_id, mod_name = _UNATTRIBUTED_ID, _UNATTRIBUTED_NAME
                    attribution = "unattributed"
                    confidence = "low"
                    why = "No direct marker and no unique recent-context match."

            if raw_mod_name:
                confidence = "high"
                why = "Matched explicit Lua((MOD:...)) marker in line/stack context."

            fpath, lineno = _extract_file_line([raw] + stack)
            target = report.errors if severity == "error" else report.warns
            kind = "engine_noise" if _is_engine_noise_message(msg) else "runtime"
            _upsert_issue(
                target,
                mod_id=mod_id,
                mod_name=mod_name,
                severity=severity,
                message=msg,
                file=fpath,
                line=lineno,
                stack=stack,
                kind=kind,
                attribution=attribution,
                confidence=confidence,
                attribution_reason=why,
                cause_chain=cause_chain,
            )

        i += 1

    return report


def run_inspection(mods, console_path: Path | None = None):
    """Returns (report, func_conflicts=[]) — kept for API compat with app.py."""
    name_map = {m.id: m.name for m in mods}
    if console_path and console_path.exists():
        report = parse_console(console_path, name_map)
    else:
        report = ConsoleReport()

    if mods and (report.errors or report.warns):
        _reattribute_unattributed(report, mods, name_map)

    # Filter to only currently-active mods. console.txt persists across
    # sessions so removed mods would still appear otherwise.
    if mods:
        active = {_norm_mod_key(m.name) for m in mods} | {_norm_mod_key(m.id) for m in mods}
        active.add(_norm_mod_key(_UNATTRIBUTED_ID))
        active.add(_norm_mod_key(_UNATTRIBUTED_NAME))
        report.errors = [
            e for e in report.errors
            if (
                _norm_mod_key(e.mod_name) in active
                or _norm_mod_key(e.mod_id) in active
                or e.mod_id == _UNATTRIBUTED_ID
            )
        ]
        report.warns = [
            e for e in report.warns
            if (
                _norm_mod_key(e.mod_name) in active
                or _norm_mod_key(e.mod_id) in active
                or e.mod_id == _UNATTRIBUTED_ID
            )
        ]

    return report, []
