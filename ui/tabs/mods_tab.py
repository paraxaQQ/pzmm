"""Mods tab — searchable table of all scanned mods with enable/disable toggles."""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QTableWidget, QTableWidgetItem, QLabel, QHeaderView, QMenu,
    QPushButton, QCheckBox, QMessageBox, QInputDialog, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction
from ui.style import COLOR_OK, COLOR_WARN, COLOR_ERROR, COLOR_DIM, COLOR_ACCENT
from ui.tabs.ai_tab import Attachment
from ui.version_port_dialog import VersionPortDialog
from ui import fs_util
from core import config as config_mod
from core import porting
from core.modmanager_io import write_modmanager_mods


class ModsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._mods: list = []                    # ALL mods (workshop + local)
        self._active_ids: set[str] = set()       # ids currently in modmanager-mods.txt
        self._pending: dict[str, bool] = {}      # id -> desired active state (only if differs from current)
        self._err_by_mod: dict = {}
        self._fc_map:     dict = {}
        self._id_counts:  dict[str, int] = {}
        self._load_order: list[str] = []         # solved load order from scan
        self._zomboid_root: str = ""
        self._local_mods_dirs: list[Path] = []
        self._ai_tab = None
        self._tabs = None
        self._ai_features_enabled = False
        self._conflicts_tab = None
        self._request_rescan = None
        self._build()

    def set_ai_tab(self, ai_tab, tabs_widget):
        self._ai_tab = ai_tab
        self._tabs = tabs_widget

    def set_ai_enabled(self, enabled: bool):
        self._ai_features_enabled = bool(enabled)

    def set_conflicts_tab(self, conflicts_tab):
        self._conflicts_tab = conflicts_tab

    def set_rescan_handler(self, fn):
        self._request_rescan = fn

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # ── Top row: search + filters ────────────────────────────────────────
        top = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search mods…")
        self._search.textChanged.connect(self._apply_filters)
        top.addWidget(self._search)

        self._active_only = QCheckBox("Active only")
        self._active_only.setChecked(False)
        self._active_only.setToolTip("Hide inactive mods")
        self._active_only.toggled.connect(self._apply_filters)
        top.addWidget(self._active_only)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #555570; font-size: 12px; background: transparent;")
        top.addWidget(self._count_lbl)
        lay.addLayout(top)

        # ── Table ────────────────────────────────────────────────────────────
        cols = ["Active", "Name", "ID", "Source", "PZ Ver", "Errors", "File Conflicts", "Status"]
        self._table = QTableWidget(0, len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in range(2, len(cols)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self._table)

        # ── Bottom row: pending changes + apply ──────────────────────────────
        bot = QHBoxLayout()
        self._pending_lbl = QLabel("")
        self._pending_lbl.setStyleSheet(f"color: {COLOR_WARN}; font-weight: 600;")
        bot.addWidget(self._pending_lbl)
        bot.addStretch()

        self._undo_btn = QPushButton("Undo changes")
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self._undo_pending)
        bot.addWidget(self._undo_btn)

        self._apply_btn = QPushButton("Apply changes")
        self._apply_btn.setToolTip("Write the enabled mod set to modmanager-mods.txt")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply_changes)
        bot.addWidget(self._apply_btn)
        lay.addLayout(bot)

    # ── Populate ──────────────────────────────────────────────────────────────

    def update_results(self, scan_result: dict):
        # Full mod list (active + inactive), with scan-derived stats
        all_mods   = scan_result.get("all_mods") or scan_result["mods"]
        file_conf  = scan_result.get("file_conflicts", [])
        report     = scan_result.get("console_report")
        dep        = scan_result.get("dep_graph")
        active_mods = scan_result.get("mods", [])

        self._mods = all_mods
        self._id_counts = {}
        for m in all_mods:
            self._id_counts[m.id] = self._id_counts.get(m.id, 0) + 1
        self._err_by_mod = report.by_mod if report else {}
        self._active_ids = {m.id for m in active_mods}
        self._pending.clear()
        self._zomboid_root = scan_result.get("zomboid_root", "")
        self._local_mods_dirs = [Path(p) for p in scan_result.get("local_dirs", []) if p]
        self._load_order = list(dep.order) if dep else [m.id for m in active_mods]

        # Build lookup maps
        err_map:  dict[str, int] = {}
        warn_map: dict[str, int] = {}
        if report:
            for e in report.errors:
                err_map[e.mod_id] = err_map.get(e.mod_id, 0) + max(1, getattr(e, "occurrence_count", 1))
            for e in report.warns:
                warn_map[e.mod_id] = warn_map.get(e.mod_id, 0) + max(1, getattr(e, "occurrence_count", 1))
        self._fc_map = {}
        for fc in file_conf:
            for prov in fc.providers:
                self._fc_map[prov.id] = self._fc_map.get(prov.id, 0) + 1

        # Repaint table — disable sorting + itemChanged spam during bulk load
        self._table.setSortingEnabled(False)
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(len(all_mods))
            for row, mod in enumerate(all_mods):
                self._fill_row(row, mod, err_map, warn_map)
        finally:
            self._table.blockSignals(False)
            self._table.setSortingEnabled(True)

        self._refresh_pending_ui()
        self._apply_filters()

    def _fill_row(self, row: int, mod, err_map, warn_map):
        is_active = mod.id in self._active_ids
        mod_key = mod.id.lower().replace(" ", "").replace("'", "").replace("-", "")
        n_err  = err_map.get(mod_key, 0)
        n_warn = warn_map.get(mod_key, 0)
        fc     = self._fc_map.get(mod.id, 0)

        if not is_active:
            status, scol = "INACTIVE", COLOR_DIM
        elif n_err > 0:
            status, scol = "ERRORS",   COLOR_ERROR
        elif n_warn > 0:
            status, scol = "WARNINGS", COLOR_WARN
        elif fc > 0:
            status, scol = "CONFLICTS", COLOR_WARN
        else:
            status, scol = "OK", COLOR_OK

        err_str  = str(n_err)  if n_err  else "—"
        fc_str   = str(fc)     if fc     else "—"

        # Active checkbox — built as a standalone checkable QTableWidgetItem so
        # sorting + clicks Just Work without a cellWidget layering dance.
        chk = QTableWidgetItem()
        chk.setFlags(
            Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        chk.setCheckState(Qt.CheckState.Checked if is_active else Qt.CheckState.Unchecked)
        chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        # Stash the mod id on the checkbox item so _on_item_changed can find it
        chk.setData(Qt.ItemDataRole.UserRole, mod.id)
        self._table.setItem(row, 0, chk)

        name_text = mod.name
        if self._id_counts.get(mod.id, 0) > 1:
            if mod.source == "workshop":
                key = "Workshop"
            else:
                key = "Local clone"
            name_text = f"{mod.name} [{key}]"
        name_item = self._cell(name_text)
        name_item.setToolTip(f"{mod.name}\nsource={mod.source}\npath={mod.path}")
        self._table.setItem(row, 1, name_item)
        id_item = self._cell(mod.id, COLOR_DIM)
        id_item.setData(Qt.ItemDataRole.UserRole, str(mod.path))
        id_item.setData(Qt.ItemDataRole.UserRole + 1, mod.source)
        self._table.setItem(row, 2, id_item)
        self._table.setItem(row, 3, self._cell(mod.source, COLOR_DIM))
        self._table.setItem(row, 4, self._cell(mod.pz_version, COLOR_DIM))
        self._table.setItem(row, 5, self._cell(
            err_str, COLOR_ERROR if n_err else COLOR_DIM, Qt.AlignmentFlag.AlignHCenter
        ))
        self._table.setItem(row, 6, self._cell(
            fc_str, COLOR_WARN if fc else COLOR_DIM, Qt.AlignmentFlag.AlignHCenter
        ))
        self._table.setItem(row, 7, self._cell(status, scol, Qt.AlignmentFlag.AlignHCenter))

    def _cell(self, text: str, color: str | None = None,
              align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        if color:
            item.setForeground(QColor(color))
        return item

    # ── Checkbox toggles → pending changes ───────────────────────────────────

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != 0:
            return
        mod_id = item.data(Qt.ItemDataRole.UserRole)
        if not mod_id:
            return
        desired = item.checkState() == Qt.CheckState.Checked
        currently = mod_id in self._active_ids
        if desired == currently:
            self._pending.pop(mod_id, None)
        else:
            self._pending[mod_id] = desired
        self._refresh_pending_ui()

    def _refresh_pending_ui(self):
        n = len(self._pending)
        if n == 0:
            self._pending_lbl.setText("")
            self._apply_btn.setEnabled(False)
            self._undo_btn.setEnabled(False)
            return
        n_enable  = sum(1 for v in self._pending.values() if v)
        n_disable = n - n_enable
        parts = []
        if n_enable:  parts.append(f"+{n_enable} enable")
        if n_disable: parts.append(f"-{n_disable} disable")
        self._pending_lbl.setText(f"Pending: {', '.join(parts)}")
        self._apply_btn.setEnabled(bool(self._zomboid_root))
        self._undo_btn.setEnabled(True)

    def _undo_pending(self):
        # Reset each pending row's checkbox to its original state
        self._table.blockSignals(True)
        try:
            for row in range(self._table.rowCount()):
                it = self._table.item(row, 0)
                if it is None:
                    continue
                mod_id = it.data(Qt.ItemDataRole.UserRole)
                if mod_id not in self._pending:
                    continue
                was_active = mod_id in self._active_ids
                it.setCheckState(Qt.CheckState.Checked if was_active else Qt.CheckState.Unchecked)
        finally:
            self._table.blockSignals(False)
        self._pending.clear()
        self._refresh_pending_ui()

    def _apply_changes(self):
        if not self._pending:
            return
        if not self._zomboid_root:
            QMessageBox.warning(self, "Apply", "Zomboid root not detected — can't write.")
            return

        # Compute desired active set
        desired_active: set[str] = set(self._active_ids)
        for mid, on in self._pending.items():
            if on:
                desired_active.add(mid)
            else:
                desired_active.discard(mid)

        # Preserve the scan's solved load order, then append newly-enabled mods
        ordered: list[str] = []
        seen: set[str] = set()
        for mid in self._load_order:
            if mid in desired_active and mid not in seen:
                ordered.append(mid)
                seen.add(mid)
        for mid in sorted(desired_active - seen):
            ordered.append(mid)
            seen.add(mid)

        p = Path(self._zomboid_root) / "Lua" / "modmanager-mods.txt"
        try:
            wr = write_modmanager_mods(p, ordered, session_id="mods-tab")
        except Exception as e:
            QMessageBox.critical(self, "Apply failed", str(e))
            return

        self._active_ids = desired_active
        self._pending.clear()
        self._refresh_pending_ui()
        QMessageBox.information(
            self, "Applied",
            f"Active mod set written to:\n{p}\n\n"
            + (f"Backup created: {wr.backup_path.name}\n\n" if wr.backup_path else "")
            +
            f"{len(desired_active)} mods enabled. Restart PZ for changes to take effect, "
            f"or rescan here to refresh errors/conflicts."
        )

    # ── Filtering ────────────────────────────────────────────────────────────

    def _apply_filters(self):
        text = self._search.text().lower()
        active_only = self._active_only.isChecked()
        visible = 0
        for row in range(self._table.rowCount()):
            name = (self._table.item(row, 1) or QTableWidgetItem("")).text().lower()
            mid  = (self._table.item(row, 2) or QTableWidgetItem("")).text().lower()
            chk  = self._table.item(row, 0)
            is_active = bool(chk and chk.checkState() == Qt.CheckState.Checked)
            hide = False
            if text and text not in name and text not in mid:
                hide = True
            if active_only and not is_active:
                hide = True
            self._table.setRowHidden(row, hide)
            if not hide:
                visible += 1
        total  = self._table.rowCount()
        active = sum(1 for r in range(total)
                     if (c := self._table.item(r, 0)) and c.checkState() == Qt.CheckState.Checked)
        self._count_lbl.setText(f"{visible} shown  |  {active} active  |  {total} total")

    # ── Right-click → context menu ───────────────────────────────────────────

    def _on_context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        id_item = self._table.item(row, 2)
        src_item = self._table.item(row, 3)
        if id_item is None:
            return
        mod_id = id_item.text()
        row_source = src_item.text() if src_item is not None else ""
        row_path = id_item.data(Qt.ItemDataRole.UserRole) or ""

        mod = next(
            (
                m for m in self._mods
                if m.id == mod_id
                and (not row_source or m.source == row_source)
                and (not row_path or str(m.path) == str(row_path))
            ),
            None,
        )
        if mod is None:
            # Fallback if row metadata is missing (older rows)
            mod = next((m for m in self._mods if m.id == mod_id and (not row_source or m.source == row_source)), None)
        if mod is None:
            return

        menu = QMenu(self)
        act_info = None
        act_debug = None
        ai_available = self._ai_features_enabled and self._ai_tab is not None
        if ai_available:
            act_info = QAction("Ask AI about this mod", self)
            act_debug = QAction("Debug this mod with AI  (errors + key files)", self)
            menu.addAction(act_info)
            menu.addAction(act_debug)
            menu.addSeparator()
        act_open_folder = QAction("Open mod folder", self)
        act_open_folder.setEnabled(mod.path.exists())
        menu.addAction(act_open_folder)
        act_open_info = QAction("Open mod.info in editor", self)
        info_path = mod.path / "mod.info"
        act_open_info.setEnabled(info_path.exists())
        menu.addAction(act_open_info)
        act_port_label = "Port Version Folder..." if mod.source == "local" else "Clone To Local + Port..."
        act_port = QAction(act_port_label, self)
        # Keep this clickable so users get an explicit reason if unavailable.
        act_port.setEnabled(True)
        act_port.setToolTip(
            "Local: port directly. Workshop: clone to local mods folder, then port."
        )
        menu.addAction(act_port)
        fc_count = self._fc_map.get(mod.id, 0)
        act_conflicts = QAction(f"View file conflicts ({fc_count})", self)
        act_conflicts.setEnabled(fc_count > 0 and self._tabs is not None and self._conflicts_tab is not None)
        menu.addAction(act_conflicts)
        menu.addSeparator()
        chk_item = self._table.item(row, 0)
        is_active = bool(chk_item and chk_item.checkState() == Qt.CheckState.Checked)
        act_toggle = QAction("Disable this mod" if is_active else "Enable this mod", self)
        menu.addAction(act_toggle)

        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if act_info is not None and (chosen == act_info or chosen == act_debug):
            self._send_mod_to_ai(mod, full=(chosen == act_debug))
        elif chosen == act_open_folder:
            fs_util.open_folder(mod.path)
        elif chosen == act_open_info:
            cfg = config_mod.load()
            fs_util.open_in_editor(info_path, cfg.external_editor)
        elif chosen == act_port:
            self._open_port_dialog(mod)
        elif chosen == act_conflicts and self._tabs is not None and self._conflicts_tab is not None:
            self._conflicts_tab.focus_mod(mod.id)
            for i in range(self._tabs.count()):
                if self._tabs.tabText(i) == "Conflicts":
                    self._tabs.setCurrentIndex(i)
                    break
        elif chosen == act_toggle and chk_item is not None:
            chk_item.setCheckState(
                Qt.CheckState.Unchecked if is_active else Qt.CheckState.Checked
            )

    def _send_mod_to_ai(self, mod, full: bool):
        info_path = mod.path / "mod.info"
        if info_path.exists():
            try:
                self._ai_tab.add_attachment(Attachment(
                    kind="mod",
                    title=f"{mod.name} — mod.info",
                    content=info_path.read_text(encoding="utf-8", errors="ignore"),
                ))
            except Exception:
                pass

        if full:
            norm = lambda s: s.lower().replace(" ", "").replace("'", "").replace("-", "")
            key_candidates = {norm(mod.name), norm(mod.id)}
            err_entries = []
            for k, entries in self._err_by_mod.items():
                if k in key_candidates:
                    err_entries.extend(entries)

            if err_entries:
                lines = []
                for e in err_entries[:10]:
                    occ = max(1, getattr(e, "occurrence_count", 1))
                    occ_txt = f" (x{occ})" if occ > 1 else ""
                    kind = getattr(e, "kind", "")
                    kind_txt = f" [{kind}]" if kind else ""
                    attr = getattr(e, "attribution", "")
                    attr_txt = f" [{attr}]" if attr else ""
                    lines.append(f"[{e.severity.upper()}]{kind_txt}{attr_txt} {e.message}{occ_txt}")
                    if getattr(e, "cause_chain", ""):
                        lines.append(f"  cause: {e.cause_chain}")
                    if e.file:
                        lines.append(f"  at {e.file}" + (f":{e.line}" if e.line else ""))
                    if e.stack:
                        lines.extend(f"    {s}" for s in e.stack[:5])
                    lines.append("")
                total_occ = sum(max(1, getattr(e, "occurrence_count", 1)) for e in err_entries)
                self._ai_tab.add_attachment(Attachment(
                    kind="error",
                    title=f"{mod.name} — {total_occ} console errors",
                    content="\n".join(lines),
                ))

            for lua_name in ("BodyLocations.lua", "registries.lua"):
                for p in mod.path.rglob(f"*{lua_name}"):
                    if p.is_file():
                        try:
                            self._ai_tab.add_attachment(Attachment(
                                kind="file",
                                title=f"{p.name}  ({p.parent.name})",
                                content=p.read_text(encoding="utf-8", errors="ignore"),
                            ))
                        except Exception:
                            pass
                        break

        if self._tabs:
            switched = False
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

    def _open_port_dialog(self, mod):
        if mod.source == "workshop":
            if not self._local_mods_dirs:
                QMessageBox.information(
                    self,
                    "Clone unavailable",
                    "No local mods folder was detected. Create/use Zomboid\\mods and rescan.",
                )
                return
            local_root = self._choose_local_mods_dir()
            if local_root is None:
                return
            answer = QMessageBox.question(
                self,
                "Clone to local and port",
                f"This workshop mod will be cloned to:\n{local_root}\n\n"
                "Then porting runs on the local clone. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                cloned_root = porting.clone_mod_root_to_local(
                    mod.path,
                    local_root,
                    preferred_name=mod.name,
                )
            except Exception as e:
                QMessageBox.warning(self, "Clone failed", str(e))
                return
            # Open the clone so users can immediately verify where edits happen.
            fs_util.open_folder(cloned_root)
            try:
                layout = porting.discover_version_layout(cloned_root)
            except Exception as e:
                QMessageBox.warning(self, "Porting", f"Could not inspect cloned layout:\n{e}")
                return
            if not layout.versions:
                QMessageBox.information(
                    self,
                    "Porting unavailable",
                    "Clone succeeded, but no versioned subfolders were found.",
                )
                return
            QMessageBox.information(
                self,
                "Clone complete",
                f"Cloned to:\n{cloned_root}\n\nOpening port dialog for the clone.",
            )
            dlg = VersionPortDialog(
                mod_name=f"{mod.name} (local clone)",
                mod_root=layout.mod_root,
                versions=layout.versions,
                parent=self,
            )
            if dlg.exec():
                QMessageBox.information(
                    self,
                    "Porting",
                    "Port completed on the local clone. The app will rescan now.",
                )
                self._offer_workshop_ready_export(layout.mod_root, mod.name)
                if self._request_rescan is not None:
                    self._request_rescan()
            else:
                # Clone still succeeded; refresh so local copy appears in Mods list.
                if self._request_rescan is not None:
                    self._request_rescan()
            return

        if mod.source != "local":
            QMessageBox.information(self, "Porting unavailable", f"Unsupported mod source: {mod.source}")
            return
        try:
            layout = porting.discover_version_layout(mod.path)
        except Exception as e:
            QMessageBox.warning(self, "Porting", f"Could not inspect mod layout:\n{e}")
            return
        if not layout.versions:
            QMessageBox.information(
                self,
                "Porting unavailable",
                "No versioned subfolders were found for this mod.",
            )
            return
        dlg = VersionPortDialog(
            mod_name=mod.name,
            mod_root=layout.mod_root,
            versions=layout.versions,
            parent=self,
        )
        if dlg.exec():
            QMessageBox.information(
                self,
                "Porting",
                "Port completed. The app will rescan now.",
            )
            self._offer_workshop_ready_export(layout.mod_root, mod.name)
            if self._request_rescan is not None:
                self._request_rescan()

    def _choose_local_mods_dir(self) -> Path | None:
        if not self._local_mods_dirs:
            return None
        if len(self._local_mods_dirs) == 1:
            return self._local_mods_dirs[0]
        options = [str(p) for p in self._local_mods_dirs]
        chosen, ok = QInputDialog.getItem(
            self,
            "Choose local mods folder",
            "Clone destination:",
            options,
            0,
            False,
        )
        if not ok or not chosen:
            return None
        return Path(chosen)

    def _offer_workshop_ready_export(self, mod_root: Path, mod_name: str):
        answer = QMessageBox.question(
            self,
            "Workshop-ready export",
            "Create a workshop-ready copy now?\n\n"
            "This exports a clean copy (excluding .pzmm manifests/backups).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        out_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose export parent folder",
            str(mod_root.parent),
        )
        if not out_dir:
            return
        try:
            exported = porting.export_workshop_ready_copy(
                mod_root,
                Path(out_dir),
                preferred_name=mod_name,
            )
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        QMessageBox.information(
            self,
            "Workshop-ready export complete",
            f"Exported to:\n{exported}\n\n"
            "Respect each mod author's permissions before publishing.",
        )
