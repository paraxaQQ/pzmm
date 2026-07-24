"""Heuristic scanner for suspicious mod content.

This stays local-only for v1: it does lightweight text and filename checks and
returns a risk level. It is not antivirus software.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter, time
from typing import Iterable

_TEXT_EXTENSIONS = {
    ".lua",
    ".txt",
    ".xml",
    ".json",
    ".ini",
    ".cfg",
    ".md",
    ".yml",
    ".yaml",
}

_BLOCKED_EXTENSIONS = {
    ".exe",
    ".dll",
    ".com",
    ".scr",
    ".ps1",
    ".bat",
    ".cmd",
    ".vbs",
    ".js",
    ".jar",
}

_SUSPECT_FILENAME_TOKENS = (
    "inject",
    "backdoor",
    "payload",
    "keygen",
    "miner",
    "keylogger",
    "rat",
    "rootkit",
)

_MAX_FILE_SCAN_BYTES = 2 * 1024 * 1024

_SKIP_DIR_PARTS = {".git", "__pycache__", ".svn", "node_modules"}

_PATTERN_RULES = [
    (re.compile(r"\bos\.execute\(", re.IGNORECASE), "high", "OS_EXECUTE"),
    (re.compile(r"\bio\.popen\(", re.IGNORECASE), "high", "IO_POPEN"),
    (re.compile(r"\bloadstring\s*\(", re.IGNORECASE), "high", "LUA_LOADSTRING"),
    (re.compile(r"\bloadfile\s*\(", re.IGNORECASE), "high", "LUA_LOADFILE"),
    (re.compile(r"\bpackage\.loadlib", re.IGNORECASE), "high", "PKG_LOADLIB"),
    (re.compile(r"\bdofile\s*\(", re.IGNORECASE), "high", "LUA_DFILE"),
    (re.compile(r"\brequire\s*\(\s*['\"]https?://", re.IGNORECASE), "medium", "REMOTE_REQUIRE"),
    (re.compile(r"\bsocket\.", re.IGNORECASE), "medium", "NETWORK_SOCKET"),
    (re.compile(r"\bhttp\.(?:get|post)\s*\(", re.IGNORECASE), "medium", "HTTP_REQUEST"),
    (re.compile(r"\blua\s+do\s+string", re.IGNORECASE), "medium", "LUA_DYN"),
    (re.compile(r"\bstring\.char\(", re.IGNORECASE), "low", "STRING_CHAR"),
]


def _config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "pzmm"
    return Path.home() / ".config" / "pzmm"


def _cache_path() -> Path:
    return _config_dir() / "virus_scans.json"


def _cache_key(path: Path) -> str:
    return str(path.resolve()).lower()


def _read_cache() -> dict[str, dict]:
    p = _cache_path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        return {}
    return {}


def _write_cache(cache: dict[str, dict]) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=2), encoding="utf-8")


@dataclass
class VirusScanFinding:
    path: str
    rule: str
    severity: str
    detail: str


@dataclass
class VirusScanResult:
    mod_id: str
    mod_path: str
    risk_level: str
    status: str
    findings: list[VirusScanFinding] = field(default_factory=list)
    scanned_at: float = 0.0
    elapsed_ms: float = 0.0
    engine: str = "heuristic"
    fingerprint: str = ""
    from_cache: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["findings"] = [asdict(f) for f in self.findings]
        return payload

    @staticmethod
    def from_dict(data: dict) -> VirusScanResult:
        findings = []
        for item in data.get("findings", []):
            if isinstance(item, dict):
                findings.append(VirusScanFinding(
                    path=str(item.get("path", "")),
                    rule=str(item.get("rule", "")),
                    severity=str(item.get("severity", "low")),
                    detail=str(item.get("detail", "")),
                ))
        return VirusScanResult(
            mod_id=str(data.get("mod_id", "")),
            mod_path=str(data.get("mod_path", "")),
            risk_level=str(data.get("risk_level", "unknown")),
            status=str(data.get("status", "unknown")),
            findings=findings,
            scanned_at=float(data.get("scanned_at", 0.0)),
            elapsed_ms=float(data.get("elapsed_ms", 0.0)),
            engine=str(data.get("engine", "heuristic")),
            fingerprint=str(data.get("fingerprint", "")),
            from_cache=bool(data.get("from_cache", False)),
            error=str(data.get("error", "")),
        )


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part.lower() in _SKIP_DIR_PARTS:
            return True
    return False


def _iter_scanned_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if _should_skip(p):
            continue
        yield p


def _fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    for file_path in sorted(_iter_scanned_files(path), key=lambda p: str(p).lower()):
        rel = file_path.relative_to(path).as_posix().lower()
        try:
            st = file_path.stat()
        except Exception:
            continue
        h.update(rel.encode("utf-8", errors="ignore"))
        h.update(str(st.st_size).encode("ascii"))
        h.update(str(st.st_mtime_ns).encode("ascii"))
    return h.hexdigest()


def _risk_for_findings(max_severity: str) -> tuple[str, str]:
    if max_severity == "high":
        return "high", "high_risk"
    if max_severity == "medium":
        return "medium", "warning"
    if max_severity == "low":
        return "low", "warning"
    return "safe", "clean"


def _scan_file(path: Path, rel: Path, findings: list[VirusScanFinding], risk_bucket: dict[str, bool]) -> None:
    name = path.name.lower()
    ext = path.suffix.lower()
    if ext in _BLOCKED_EXTENSIONS:
        findings.append(
            VirusScanFinding(
                path=str(rel),
                rule="BLOCKED_EXTENSION",
                severity="high",
                detail=f"blocked executable type: {path.suffix.lower()}",
            )
        )
        risk_bucket["high"] = True
        return

    if any(token in name for token in _SUSPECT_FILENAME_TOKENS):
        findings.append(
            VirusScanFinding(
                path=str(rel),
                rule="SUSPECT_FILENAME",
                severity="medium",
                detail=f"suspicious filename token in {path.name}",
            )
        )
        risk_bucket["medium"] = True

    if ext not in _TEXT_EXTENSIONS:
        return

    try:
        size = path.stat().st_size
    except Exception:
        return
    if size > _MAX_FILE_SCAN_BYTES:
        findings.append(
            VirusScanFinding(
                path=str(rel),
                rule="LARGE_FILE_SKIPPED",
                severity="low",
                detail=f"skipped over-large file ({size} bytes)",
            )
        )
        return

    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return

    for regex, severity, rule in _PATTERN_RULES:
        if not regex.search(text):
            continue
        findings.append(
            VirusScanFinding(
                path=str(rel),
                rule=rule,
                severity=severity,
                detail=f"suspicious pattern detected: {rule}",
            )
        )
        risk_bucket[severity] = True


def _load_cache_entry(cache: dict[str, dict], path: Path, current_fingerprint: str) -> VirusScanResult | None:
    key = _cache_key(path)
    entry = cache.get(key)
    if not isinstance(entry, dict):
        return None
    if entry.get("fingerprint", "") != current_fingerprint:
        return None
    payload = entry.get("result")
    if not isinstance(payload, dict):
        return None
    try:
        result = VirusScanResult.from_dict(payload)
    except Exception:
        return None
    result.from_cache = True
    return result


def _store_cache_entry(cache: dict[str, dict], result: VirusScanResult) -> None:
    cache[_cache_key(Path(result.mod_path))] = {
        "fingerprint": result.fingerprint,
        "result": result.to_dict(),
    }


def scan_mod(
    mod_path: Path | str,
    mod_id: str = "",
    mod_name: str = "",
    *,
    force: bool = False,
) -> VirusScanResult:
    root = Path(mod_path)
    start = perf_counter()
    payload_path = str(root.resolve()) if root.exists() else str(root)
    if not root.exists():
        return VirusScanResult(
            mod_id=mod_id,
            mod_path=payload_path,
            risk_level="error",
            status="error",
            scanned_at=time(),
            elapsed_ms=0.0,
            error="mod path does not exist",
            fingerprint="",
        )
    if not root.is_dir():
        return VirusScanResult(
            mod_id=mod_id,
            mod_path=payload_path,
            risk_level="error",
            status="error",
            scanned_at=time(),
            elapsed_ms=0.0,
            error="mod path is not a directory",
            fingerprint="",
        )

    cache = _read_cache()
    fingerprint = _fingerprint(root)

    if not force:
        cached = _load_cache_entry(cache, root, fingerprint)
        if cached is not None:
            return cached

    findings: list[VirusScanFinding] = []
    risk_bucket: dict[str, bool] = {"low": False, "medium": False, "high": False}

    for p in _iter_scanned_files(root):
        rel = p.relative_to(root)
        _scan_file(p, rel, findings, risk_bucket)

    if risk_bucket["high"]:
        max_sev = "high"
    elif risk_bucket["medium"]:
        max_sev = "medium"
    elif risk_bucket["low"]:
        max_sev = "low"
    else:
        max_sev = "safe"

    risk_level, status = _risk_for_findings(max_sev)
    result = VirusScanResult(
        mod_id=mod_id,
        mod_path=payload_path,
        risk_level=risk_level,
        status=status,
        findings=findings,
        scanned_at=time(),
        elapsed_ms=(perf_counter() - start) * 1000.0,
        engine="heuristic-v1",
        fingerprint=fingerprint,
        from_cache=False,
        error="",
    )
    # Keep friendly labels for manual scans too (even if no explicit mod name was passed).
    if not result.mod_id and mod_name:
        result.mod_id = mod_name

    cache[_cache_key(root)] = {
        "fingerprint": fingerprint,
        "result": result.to_dict(),
    }
    _write_cache(cache)

    return result


def scan_mods(
    mods: list,
    *,
    include_sources: set[str] | None = None,
    force: bool = False,
    include_non_workshop: bool = True,
) -> dict[str, VirusScanResult]:
    results: dict[str, VirusScanResult] = {}
    for mod in mods:
        source = str(getattr(mod, "source", ""))
        if include_sources is not None and source not in include_sources:
            continue
        if not include_non_workshop and source != "workshop":
            continue
        path = getattr(mod, "path", None)
        if not path:
            continue
        path = Path(path)
        result = scan_mod(
            path,
            mod_id=str(getattr(mod, "id", "")),
            mod_name=str(getattr(mod, "name", "")),
            force=force,
        )
        results[str(path)] = result
    return results
