"""Build a debug bundle (zip) — console.txt + active mod.info files + report.

Designed to drop into a bug report / Discord post so someone helping can see
the full picture without asking the user to paste 20 things.
"""
from __future__ import annotations
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

from core import __version__ as PZMM_VERSION


def _build_report_text(scan_result: dict) -> str:
    mods      = scan_result.get("mods", [])
    file_conf = scan_result.get("file_conflicts", [])
    dep       = scan_result.get("dep_graph")
    report    = scan_result.get("console_report")
    zomboid_root  = scan_result.get("zomboid_root", "?")
    workshop_dirs = scan_result.get("workshop_dirs", [])
    local_dirs    = scan_result.get("local_dirs", [])

    n_err  = report.error_occurrences if report else 0
    n_warn = report.warn_occurrences  if report else 0
    n_cyc  = len(dep.cycles)    if dep else 0

    lines: list[str] = []
    lines.append(f"pzmm debug bundle — v{PZMM_VERSION}")
    lines.append(f"generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("── Paths ─────────────────────────────────────────────────")
    lines.append(f"Zomboid root:  {zomboid_root}")
    for w in workshop_dirs:
        lines.append(f"Workshop dir:  {w}")
    for l in local_dirs:
        lines.append(f"Local dir:     {l}")
    lines.append("")
    lines.append("── Summary ───────────────────────────────────────────────")
    lines.append(f"Active mods:       {len(mods)}")
    lines.append(f"File conflicts:    {len(file_conf)}")
    lines.append(f"Dep cycles:        {n_cyc}")
    lines.append(f"Errors (console):  {n_err}")
    lines.append(f"Warnings (console):{n_warn}")
    lines.append("")

    # ── Active mods list ──────────────────────────────────────────────────
    lines.append("── Active mods ───────────────────────────────────────────")
    for m in mods:
        lines.append(f"  {m.name}")
        lines.append(f"    id={m.id}  v={m.version}  pz={m.pz_version}  source={m.source}"
                     + (f"  workshop={m.workshop_id}" if getattr(m, "workshop_id", "") else ""))
        if getattr(m, "requires", None):
            lines.append(f"    requires: {', '.join(m.requires)}")
    lines.append("")

    # ── Errors per mod ────────────────────────────────────────────────────
    if report and report.by_mod:
        lines.append("── Errors by mod ─────────────────────────────────────────")
        for key, entries in report.by_mod.items():
            mod_name = entries[0].mod_name if entries else key
            n_e = sum(max(1, getattr(e, "occurrence_count", 1)) for e in entries if e.severity == "error")
            n_w = sum(max(1, getattr(e, "occurrence_count", 1)) for e in entries if e.severity != "error")
            lines.append(f"  {mod_name}  [{n_e}E {n_w}W]")
            for e in entries[:8]:
                loc = (e.file or "") + (f":{e.line}" if e.line else "")
                occ = max(1, getattr(e, "occurrence_count", 1))
                occ_txt = f" (x{occ})" if occ > 1 else ""
                kind = getattr(e, "kind", "")
                kind_txt = f" [{kind}]" if kind else ""
                attr = getattr(e, "attribution", "")
                attr_txt = f" [{attr}]" if attr else ""
                lines.append(f"    [{e.severity.upper()}]{kind_txt}{attr_txt} {e.message}{occ_txt}"
                             + (f"  @ {loc}" if loc else ""))
                if getattr(e, "cause_chain", ""):
                    lines.append(f"       cause: {e.cause_chain}")
                for s in (e.stack or [])[:3]:
                    lines.append(f"       {s}")
            if len(entries) > 8:
                lines.append(f"    … {len(entries) - 8} more")
        lines.append("")

    # ── File conflicts ────────────────────────────────────────────────────
    if file_conf:
        lines.append("── File conflicts ────────────────────────────────────────")
        for c in file_conf[:40]:
            providers = ", ".join(p.name for p in c.providers)
            lines.append(f"  {c.rel_path}  ({providers})")
        if len(file_conf) > 40:
            lines.append(f"  … {len(file_conf) - 40} more")
        lines.append("")

    # ── Dep cycles ────────────────────────────────────────────────────────
    if dep and dep.cycles:
        by_id = {m.id: m for m in mods}
        lines.append("── Dependency cycles ─────────────────────────────────────")
        for cid in dep.cycles:
            lines.append(f"  {by_id[cid].name if cid in by_id else cid}  ({cid})")
        lines.append("")

    return "\n".join(lines)


def build_bundle(scan_result: dict, out_path: Path) -> tuple[int, int]:
    """Write a zip to `out_path`.

    Returns (n_mod_info_files_included, total_bytes_written).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report_text = _build_report_text(scan_result)
    mods = scan_result.get("mods", [])
    zomboid_root = scan_result.get("zomboid_root", "")

    n_info = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("pzmm-report.txt", report_text)

        # console.txt (if we can find it)
        if zomboid_root and zomboid_root != "Not found":
            console_path = Path(zomboid_root) / "console.txt"
            if console_path.exists():
                try:
                    z.write(console_path, arcname="console.txt")
                except Exception:
                    pass

        # Each active mod's mod.info
        seen_names: set[str] = set()
        for m in mods:
            info = Path(m.path) / "mod.info"
            if not info.exists():
                continue
            # Collision-safe name — just in case two mods happen to share one
            name = f"mod-info/{m.id}.info"
            i = 2
            while name in seen_names:
                name = f"mod-info/{m.id}.{i}.info"
                i += 1
            seen_names.add(name)
            try:
                z.write(info, arcname=name)
                n_info += 1
            except Exception:
                pass

        # A machine-readable index for anyone triaging the bundle
        index = {
            "pzmm_version": PZMM_VERSION,
            "generated":    datetime.now().isoformat(timespec="seconds"),
            "mods": [
                {
                    "id":       m.id,
                    "name":     m.name,
                    "version":  m.version,
                    "pz_version": m.pz_version,
                    "source":   m.source,
                }
                for m in mods
            ],
        }
        z.writestr("index.json", json.dumps(index, indent=2))

    return n_info, out_path.stat().st_size
