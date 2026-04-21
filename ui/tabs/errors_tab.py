"""Errors tab — real runtime errors parsed from console.txt, mapped to mods."""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QLabel,
    QTextEdit, QLineEdit, QHeaderView, QMenu, QSizePolicy, QHBoxLayout, QPushButton,
    QComboBox,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction, QGuiApplication
from ui.style import COLOR_ERROR, COLOR_WARN, COLOR_DIM, COLOR_ACCENT, COLOR_OK
from ui.tabs.ai_tab import Attachment
from ui.markdown_dialog import MarkdownDialog
from ui import fs_util
from core import config as config_mod
from core import error_diff as error_diff_mod


class ErrorsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._by_mod: dict = {}
        self._all_by_mod: dict = {}
        self._visible_keys: list[str] = []
        self._entries: list = []          # entries for currently-selected mod
        self._mods: list = []             # all active mods — used for file lookup
        self._last_diff: dict = {}
        self._ai_tab = None
        self._tabs = None
        self._ai_features_enabled = False
        self._on_reset_baseline = None
        self._build()

    def set_ai_tab(self, ai_tab, tabs_widget):
        self._ai_tab = ai_tab
        self._tabs = tabs_widget

    def set_ai_enabled(self, enabled: bool):
        self._ai_features_enabled = bool(enabled)
        self._send_diff_btn.setVisible(self._ai_features_enabled)

    def set_baseline_reset_handler(self, fn):
        self._on_reset_baseline = fn

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter mods…")
        self._search.textChanged.connect(self._filter)

        self._diff_mode = QComboBox()
        self._diff_mode.addItem("Everything in current log", "all")
        self._diff_mode.addItem("Changed since previous scan", "since_last")
        self._diff_mode.addItem("Changed since baseline", "since_startup")
        self._diff_mode.currentIndexChanged.connect(self._apply_diff_mode)
        self._diff_mode.setToolTip(
            "Use 'Changed since baseline' to ignore old startup noise and focus on fresh regressions."
        )

        self._help_btn = QPushButton("How to read errors")
        self._help_btn.setToolTip(
            "Open a quick guide for severity, attribution, and cause chains."
        )
        self._help_btn.clicked.connect(self._show_errors_help)
        self._send_diff_btn = QPushButton("Send diff to AI")
        self._send_diff_btn.setToolTip("Attach a scan-to-scan error diff summary to the AI tab.")
        self._send_diff_btn.clicked.connect(self._send_diff_to_ai)
        self._send_diff_btn.setVisible(False)
        self._reset_baseline_btn = QPushButton("Reset baseline")
        self._reset_baseline_btn.setToolTip(
            "Set the current error set as the new baseline for 'Changed since baseline' mode."
        )
        self._reset_baseline_btn.clicked.connect(self._reset_baseline)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self._search, stretch=1)
        top.addWidget(self._diff_mode)
        top.addWidget(self._reset_baseline_btn)
        top.addWidget(self._send_diff_btn)
        top.addWidget(self._help_btn)
        lay.addLayout(top)

        self._session_note = QLabel(
            "Note: Project Zomboid keeps appending to console.txt across sessions. "
            "For current-run-only diagnostics, launch PZ, reproduce, then rescan."
        )
        self._session_note.setWordWrap(True)
        self._session_note.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self._session_note.setStyleSheet(f"color: {COLOR_DIM}; font-size: 11px;")
        lay.addWidget(self._session_note)

        self._diff_note = QLabel("")
        self._diff_note.setWordWrap(True)
        self._diff_note.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self._diff_note.setStyleSheet(f"color: {COLOR_DIM}; font-size: 11px;")
        lay.addWidget(self._diff_note)

        h_split = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: mod list ────────────────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)
        self._mod_list = QListWidget()
        self._mod_list.currentRowChanged.connect(self._on_mod_select)
        ll.addWidget(self._mod_list)
        h_split.addWidget(left)

        # ── Right: vertical split — tree on top, full-text on bottom ─────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        v_split = QSplitter(Qt.Orientation.Vertical)

        self._detail = QTreeWidget()
        self._detail.setHeaderLabels(
            ["Message / Stack", "Severity", "Confidence", "Why", "Cause", "File", "Line"]
        )
        self._detail.setAlternatingRowColors(True)
        self._detail.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._detail.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._detail.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._detail.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self._detail.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self._detail.header().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._detail.header().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._detail.header().resizeSection(3, 300)
        self._detail.header().resizeSection(4, 280)
        self._detail.currentItemChanged.connect(self._on_item_select)
        self._detail.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._detail.customContextMenuRequested.connect(self._on_context_menu)
        v_split.addWidget(self._detail)

        self._fulltext = QTextEdit()
        self._fulltext.setReadOnly(True)
        self._fulltext.setPlaceholderText("Click an error to see the full message and stack trace…")
        self._fulltext.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._fulltext.setStyleSheet(
            "QTextEdit { font-family: Consolas, monospace; font-size: 12px;"
            " background: #1a1a2e; color: #c0c0d8; border: 1px solid #333355; }"
        )
        v_split.addWidget(self._fulltext)

        v_split.setSizes([300, 180])
        rl.addWidget(v_split)
        h_split.addWidget(right)

        h_split.setSizes([300, 640])
        lay.addWidget(h_split)

    # ── filtering ─────────────────────────────────────────────────────────────

    def _show_errors_help(self):
        guide = Path(__file__).resolve().parents[2] / "docs" / "HOW_TO_READ_ERRORS.md"
        dlg = MarkdownDialog("How To Read Errors", guide, self)
        dlg.exec()

    def _filter(self, text: str):
        text = text.lower()
        for i in range(self._mod_list.count()):
            item = self._mod_list.item(i)
            if item:
                item.setHidden(bool(text and text not in item.text().lower()))

    def _current_diff_keys(self) -> set[tuple[str, str, str, str, str, int]] | None:
        mode = str(self._diff_mode.currentData() or "all")
        diff = self._last_diff if hasattr(self, "_last_diff") else {}
        if mode == "all":
            return None
        if mode == "since_last":
            return ((((diff.get("since_last") or {}).get("new_or_grew") or {}).get("keys")) or set())
        if mode == "since_startup":
            return ((((diff.get("since_startup") or {}).get("new_or_grew") or {}).get("keys")) or set())
        return None

    def _apply_diff_mode(self):
        keys = self._current_diff_keys()
        if keys is None:
            self._by_mod = dict(self._all_by_mod)
        else:
            self._by_mod = {}
            for mod_key, entries in self._all_by_mod.items():
                keep = [e for e in entries if error_diff_mod.issue_key(e) in keys]
                if keep:
                    self._by_mod[mod_key] = keep
        self._repaint_from_current_by_mod()
        self._update_diff_note()

    def _update_diff_note(self):
        diff = self._last_diff if hasattr(self, "_last_diff") else {}
        last_new = (((diff.get("since_last") or {}).get("new_or_grew") or {}).get("occurrence_delta")) or 0
        last_res = (((diff.get("since_last") or {}).get("resolved_or_shrank") or {}).get("occurrence_delta")) or 0
        startup_new = (((diff.get("since_startup") or {}).get("new_or_grew") or {}).get("occurrence_delta")) or 0
        mode = str(self._diff_mode.currentData() or "all")
        if mode == "since_last":
            self._diff_note.setText(
                f"Since previous scan: {last_new} new or increased, {last_res} resolved or reduced."
            )
            return
        if mode == "since_startup":
            self._diff_note.setText(
                f"Since baseline: showing {startup_new} issues that are new or increased."
            )
            return
        self._diff_note.setText(
            f"Showing everything in current log. Since previous scan: {last_new} new/increased, {last_res} resolved/reduced. Since baseline: {startup_new} new/increased."
        )

    def _reset_baseline(self):
        if self._on_reset_baseline is None:
            return
        try:
            ok = bool(self._on_reset_baseline())
        except Exception:
            ok = False
        if ok:
            QMessageBox.information(
                self,
                "Baseline reset",
                "Baseline updated to the current error set. 'Changed since baseline' now starts from here.",
            )

    # ── mod selected → populate tree ──────────────────────────────────────────

    def _on_mod_select(self, row: int):
        self._detail.clear()
        self._fulltext.clear()
        self._entries = []

        if row < 0 or row >= len(self._visible_keys):
            return
        key = self._visible_keys[row]
        self._entries = self._by_mod.get(key, [])

        for e in self._entries:
            if getattr(e, "kind", "") == "engine_noise":
                sev_color = COLOR_DIM
                sev_label = "NOISE"
            else:
                sev_color = COLOR_ERROR if e.severity == "error" else COLOR_WARN
                sev_label = e.severity.upper()
            conf = (getattr(e, "confidence", "") or "").strip().lower()
            conf_label = conf.upper() if conf else ""
            if conf == "high":
                conf_color = COLOR_OK
            elif conf == "medium":
                conf_color = COLOR_WARN
            elif conf == "low":
                conf_color = COLOR_ERROR
            else:
                conf_color = COLOR_DIM
            msg = e.message
            if getattr(e, "occurrence_count", 1) > 1:
                msg = f"{msg}  (x{e.occurrence_count})"
            if getattr(e, "attribution", "direct") == "inferred":
                msg = f"{msg}  [inferred]"
            why = (getattr(e, "attribution_reason", "") or "").strip()
            candidates = [c for c in getattr(e, "candidate_mods", []) if c]
            if candidates:
                likely = ", ".join(candidates)
                why = f"{why}; likely mods: {likely}" if why else f"likely mods: {likely}"
            why_preview = why
            if len(why_preview) > 72:
                why_preview = why_preview[:69] + "..."
            cause_chain = (getattr(e, "cause_chain", "") or "").strip()
            cause_preview = cause_chain
            if len(cause_preview) > 72:
                cause_preview = cause_preview[:69] + "..."
            root = QTreeWidgetItem([
                msg,
                sev_label,
                conf_label,
                why_preview,
                cause_preview,
                e.file or "",
                str(e.line) if e.line else "",
            ])
            root.setForeground(0, QColor(sev_color))
            root.setForeground(1, QColor(sev_color))
            root.setForeground(2, QColor(conf_color))
            root.setForeground(3, QColor(COLOR_DIM))
            root.setForeground(4, QColor(COLOR_DIM))
            root.setForeground(5, QColor(COLOR_DIM))
            root.setForeground(6, QColor(COLOR_DIM))
            root.setData(0, Qt.ItemDataRole.UserRole, e)   # stash entry
            if why:
                root.setToolTip(3, why)
            if cause_chain:
                root.setToolTip(4, cause_chain)

            for s in e.stack:
                child = QTreeWidgetItem([s, "", "", "", "", "", ""])
                child.setForeground(0, QColor(COLOR_DIM))
                root.addChild(child)

            self._detail.addTopLevelItem(root)
            if e.stack:
                root.setExpanded(True)

    # ── tree item clicked → show full text ────────────────────────────────────

    def _on_item_select(self, current: QTreeWidgetItem | None, _):
        if current is None:
            self._fulltext.clear()
            return

        # Walk up to the root item to get the stored entry
        top = current
        while top.parent():
            top = top.parent()

        e = top.data(0, Qt.ItemDataRole.UserRole)
        if e is None:
            self._fulltext.setPlainText(current.text(0))
            return

        lines = []
        lines.append(f"[{e.severity.upper()}]  {e.message}")
        lines.append(f"Attribution: {getattr(e, 'attribution', 'direct')}")
        if getattr(e, "confidence", ""):
            lines.append(f"Confidence: {e.confidence}")
        if getattr(e, "attribution_reason", ""):
            lines.append(f"Why: {e.attribution_reason}")
        if getattr(e, "candidate_mods", None):
            lines.append(f"Likely mods: {', '.join(e.candidate_mods)}")
        if getattr(e, "kind", ""):
            lines.append(f"Type: {e.kind}")
        if getattr(e, "occurrence_count", 1) > 1:
            lines.append(f"Occurrences: {e.occurrence_count}")
        if getattr(e, "cause_chain", ""):
            lines.append(f"Cause chain: {e.cause_chain}")
        if e.file:
            loc = e.file + (f":{e.line}" if e.line else "")
            lines.append(f"Location: {loc}")
        if e.stack:
            lines.append("")
            lines.append("Stack trace:")
            lines.extend(f"  {s}" for s in e.stack)

        self._fulltext.setPlainText("\n".join(lines))

    # ── data update ───────────────────────────────────────────────────────────

    # ── right-click → Ask AI ──────────────────────────────────────────────────

    def _on_context_menu(self, pos):
        item = self._detail.itemAt(pos)
        if item is None:
            return

        # Walk up to the root to get the error entry
        top = item
        while top.parent():
            top = top.parent()
        e = top.data(0, Qt.ItemDataRole.UserRole)
        if e is None:
            return

        menu = QMenu(self)
        act_err = None
        act_full = None
        if self._ai_features_enabled and self._ai_tab is not None:
            act_err = QAction("Ask AI about this error", self)
            act_full = QAction("Ask AI about this error + source file", self)
            menu.addAction(act_err)
            menu.addAction(act_full)
            menu.addSeparator()

        act_copy = QAction("Copy error + stack to clipboard", self)
        menu.addAction(act_copy)

        # "Open source file" only works if we can locate the file.
        # "Open source folder" falls back to the mod's root when we can't.
        src_path = self._find_lua_file(e.mod_name, e.file) if e.file else None
        mod_root = self._find_mod_root(e.mod_name)

        act_open = QAction("Open source file in editor", self)
        act_open.setEnabled(src_path is not None)
        menu.addAction(act_open)

        act_folder = QAction(
            "Open source folder" if src_path else "Open mod folder", self)
        act_folder.setEnabled(src_path is not None or mod_root is not None)
        menu.addAction(act_folder)

        chosen = menu.exec(self._detail.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if act_err is not None and (chosen is act_err or chosen is act_full):
            self._send_to_ai(e, include_source=(chosen is act_full))
        elif chosen is act_copy:
            self._copy_error(e)
        elif chosen is act_open and src_path is not None:
            cfg = config_mod.load()
            ok, msg = fs_util.open_in_editor(src_path, cfg.external_editor)
            if not ok:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Could not open editor", msg)
        elif chosen is act_folder:
            target = src_path if src_path is not None else mod_root
            if target is not None:
                ok, msg = fs_util.open_folder(target)
                if not ok:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "Could not open folder", msg)

    def _copy_error(self, e):
        lines = [f"[{e.severity.upper()}] {e.message}"]
        lines.append(f"Attribution: {getattr(e, 'attribution', 'direct')}")
        if getattr(e, "confidence", ""):
            lines.append(f"Confidence: {e.confidence}")
        if getattr(e, "attribution_reason", ""):
            lines.append(f"Why: {e.attribution_reason}")
        if getattr(e, "candidate_mods", None):
            lines.append(f"Likely mods: {', '.join(e.candidate_mods)}")
        if getattr(e, "kind", ""):
            lines.append(f"Type: {e.kind}")
        if getattr(e, "occurrence_count", 1) > 1:
            lines.append(f"Occurrences: {e.occurrence_count}")
        if getattr(e, "cause_chain", ""):
            lines.append(f"Cause chain: {e.cause_chain}")
        if e.file:
            loc = e.file + (f":{e.line}" if e.line else "")
            lines.append(f"Location: {loc}")
        if getattr(e, "mod_name", None):
            lines.append(f"Mod: {e.mod_name}")
        if e.stack:
            lines.append("")
            lines.append("Stack trace:")
            lines.extend(f"  {s}" for s in e.stack)
        QGuiApplication.clipboard().setText("\n".join(lines))

    def _send_to_ai(self, e, include_source: bool):
        # Attach the error itself
        err_text = f"[{e.severity.upper()}] {e.message}\n"
        err_text += f"Attribution: {getattr(e, 'attribution', 'direct')}\n"
        if getattr(e, "confidence", ""):
            err_text += f"Confidence: {e.confidence}\n"
        if getattr(e, "attribution_reason", ""):
            err_text += f"Why: {e.attribution_reason}\n"
        if getattr(e, "candidate_mods", None):
            err_text += f"Likely mods: {', '.join(e.candidate_mods)}\n"
        if getattr(e, "kind", ""):
            err_text += f"Type: {e.kind}\n"
        if getattr(e, "occurrence_count", 1) > 1:
            err_text += f"Occurrences: {e.occurrence_count}\n"
        if getattr(e, "cause_chain", ""):
            err_text += f"Cause chain: {e.cause_chain}\n"
        if e.file:
            err_text += f"Location: {e.file}" + (f":{e.line}" if e.line else "") + "\n"
        if e.stack:
            err_text += "\nStack trace:\n" + "\n".join(f"  {s}" for s in e.stack)

        self._ai_tab.add_attachment(Attachment(
            kind="error",
            title=f"{e.mod_name} — {e.file or 'error'}",
            content=err_text,
        ))

        # Attach the source file if requested and findable
        if include_source and e.file:
            src = self._find_lua_file(e.mod_name, e.file)
            if src:
                try:
                    text = src.read_text(encoding="utf-8", errors="ignore")
                    self._ai_tab.add_attachment(Attachment(
                        kind="file",
                        title=f"{src.name}  ({src.parent.name})",
                        content=text,
                    ))
                except Exception:
                    pass

        # Jump to AI tab
        switched = False
        if self._tabs:
            for i in range(self._tabs.count()):
                if self._tabs.tabText(i) == "AI Assistant":
                    self._tabs.setCurrentIndex(i)
                    switched = True
                    break
        if not switched:
            QMessageBox.information(
                self,
                "AI Assistant disabled",
                "Enable AI Assistant in Settings to use this action.",
            )

    def _send_diff_to_ai(self):
        if self._ai_tab is None or not self._ai_features_enabled:
            QMessageBox.information(
                self,
                "AI Assistant disabled",
                "Enable AI Assistant in Settings to use this action.",
            )
            return

        diff = self._last_diff or {}
        last_new = (((diff.get("since_last") or {}).get("new_or_grew") or {}).get("occurrence_delta")) or 0
        last_res = (((diff.get("since_last") or {}).get("resolved_or_shrank") or {}).get("occurrence_delta")) or 0
        startup_new = (((diff.get("since_startup") or {}).get("new_or_grew") or {}).get("occurrence_delta")) or 0
        last_keys = ((((diff.get("since_last") or {}).get("new_or_grew") or {}).get("keys")) or set())

        lines = []
        lines.append("Error Diff Summary")
        lines.append("")
        lines.append(f"Since last scan: +{last_new} new/grown occurrences, -{last_res} resolved/shrunk occurrences")
        lines.append(f"Since startup baseline: +{startup_new} new/grown occurrences")
        lines.append("")
        lines.append("New or grown since last scan (top entries):")
        shown = 0
        for entries in self._all_by_mod.values():
            for e in entries:
                if error_diff_mod.issue_key(e) not in last_keys:
                    continue
                occ = max(1, getattr(e, "occurrence_count", 1))
                lines.append(f"- [{e.severity.upper()}] {e.mod_name}: {e.message} (x{occ})")
                shown += 1
                if shown >= 20:
                    break
            if shown >= 20:
                break
        if shown == 0:
            lines.append("- No new/grown entries in the current diff.")
        lines.append("")
        lines.append("Please suggest the next smallest safe fixes and an execution order.")

        self._ai_tab.add_attachment(Attachment(
            kind="note",
            title="Error diff summary",
            content="\n".join(lines),
        ))

        switched = False
        if self._tabs:
            for i in range(self._tabs.count()):
                if self._tabs.tabText(i) == "AI Assistant":
                    self._tabs.setCurrentIndex(i)
                    switched = True
                    break
        if not switched:
            QMessageBox.information(
                self,
                "AI Assistant disabled",
                "Enable AI Assistant in Settings to use this action.",
            )

    def _find_mod_root(self, mod_name: str) -> Path | None:
        """Return the mod.path for the mod whose display name matches."""
        norm = lambda s: s.lower().replace(" ", "").replace("'", "").replace("-", "")
        mod_norm = norm(mod_name)
        for m in self._mods:
            if norm(m.name) == mod_norm and getattr(m, "path", None):
                return m.path
        return None

    def _find_lua_file(self, mod_name: str, file_hint: str) -> Path | None:
        """Best-effort match: search active mods for a Lua file matching the hint.

        The parser captures things like 'ISInventoryContextMenu' (no extension) —
        that's the Lua module/scope name, not a filesystem path. We try the bare
        hint first, then with '.lua' appended, matching case-insensitively.
        """
        target = Path(file_hint).name.strip()
        if not target:
            return None
        target_lc = target.lower()
        target_lua = target_lc if target_lc.endswith(".lua") else target_lc + ".lua"

        norm = lambda s: s.lower().replace(" ", "").replace("'", "").replace("-", "")
        mod_norm = norm(mod_name)

        # Prefer the mod whose name matches, then fall back to all mods.
        exact = [m for m in self._mods if norm(m.name) == mod_norm]
        candidates = exact + [m for m in self._mods if m not in exact]

        for mod in candidates:
            if not getattr(mod, "path", None):
                continue
            # Walk once; pick first case-insensitive name match.
            for p in mod.path.rglob("*.lua"):
                if p.is_file() and p.name.lower() in (target_lc, target_lua):
                    return p
        return None

    def update_results(self, scan_result: dict):
        self._mods = scan_result.get("mods", [])
        report = scan_result["console_report"]
        self._all_by_mod = report.by_mod
        self._last_diff = scan_result.get("error_diff") or {}
        self._apply_diff_mode()

    def _repaint_from_current_by_mod(self):
        self._mod_list.clear()
        self._detail.clear()
        self._fulltext.clear()
        self._entries = []

        keys = sorted(
            self._by_mod.keys(),
            key=lambda k: (
                -sum(
                    max(1, getattr(e, "occurrence_count", 1))
                    for e in self._by_mod[k]
                    if e.severity == "error"
                ),
                -sum(max(1, getattr(e, "occurrence_count", 1)) for e in self._by_mod[k]),
            )
        )
        self._visible_keys = keys

        if not keys:
            item = QListWidgetItem("No errors found in console.txt")
            item.setForeground(QColor(COLOR_OK))
            self._mod_list.addItem(item)
            return

        for key in keys:
            entries = self._by_mod[key]
            mod_name = entries[0].mod_name
            n_err  = sum(
                max(1, getattr(e, "occurrence_count", 1))
                for e in entries
                if e.severity == "error"
            )
            n_warn = sum(
                max(1, getattr(e, "occurrence_count", 1))
                for e in entries
                if e.severity != "error"
            )

            parts = []
            if n_err:
                parts.append(f"{n_err}E")
            if n_warn:
                parts.append(f"{n_warn}W")
            label = f"{mod_name}  [{' '.join(parts)}]"

            item = QListWidgetItem(label)
            item.setForeground(QColor(COLOR_ERROR if n_err else COLOR_WARN))
            self._mod_list.addItem(item)
