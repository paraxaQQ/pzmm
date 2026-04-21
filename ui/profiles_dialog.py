"""Profiles dialog — save/load/delete mod-set snapshots."""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QInputDialog, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal

from core import profiles as profiles_mod


class ProfilesDialog(QDialog):
    """Manage saved profiles.

    Emits `apply_requested(profile_name)` when the user asks to load a profile
    into the current session (the main window then writes modmanager-mods.txt
    and re-scans).
    """
    apply_requested = pyqtSignal(str)   # profile name

    def __init__(self, parent=None, *, current_active_ids: list[str],
                 current_load_order: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Mod Profiles")
        self.resize(640, 440)
        self._active_ids = list(current_active_ids)
        self._load_order = list(current_load_order)
        self._build()
        self._refresh()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        hint = QLabel(
            "Profiles snapshot your active mod set + load order. "
            "Loading a profile writes it to modmanager-mods.txt — restart PZ for it to take effect."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8080a0; background:transparent;")
        lay.addWidget(hint)

        # Save-current row
        save_row = QHBoxLayout()
        save_row.addWidget(QLabel(
            f"<b>Current session:</b> {len(self._active_ids)} mods active"
        ))
        save_row.addStretch()
        save_btn = QPushButton("Save current as…")
        save_btn.clicked.connect(self._save_current)
        save_row.addWidget(save_btn)
        lay.addLayout(save_row)

        # Table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Profile", "Mods", "Updated"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.itemDoubleClicked.connect(lambda _i: self._load_selected())
        lay.addWidget(self._table, 1)

        # Action row
        btn_row = QHBoxLayout()
        self._load_btn = QPushButton("Load")
        self._load_btn.setToolTip("Write this profile's mod list to modmanager-mods.txt and re-scan")
        self._load_btn.clicked.connect(self._load_selected)
        btn_row.addWidget(self._load_btn)

        self._overwrite_btn = QPushButton("Overwrite with current")
        self._overwrite_btn.setToolTip("Replace this profile's snapshot with the currently active mods")
        self._overwrite_btn.clicked.connect(self._overwrite_selected)
        btn_row.addWidget(self._overwrite_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self._delete_btn)

        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._table.itemSelectionChanged.connect(self._update_buttons)
        self._update_buttons()

    # ── helpers ────────────────────────────────────────────────────────────

    def _refresh(self):
        profs = profiles_mod.list_profiles()
        self._table.setRowCount(len(profs))
        for i, pr in enumerate(profs):
            name_item = QTableWidgetItem(pr.name)
            name_item.setData(Qt.ItemDataRole.UserRole, pr.name)
            self._table.setItem(i, 0, name_item)
            self._table.setItem(i, 1, QTableWidgetItem(str(len(pr.mod_ids))))
            self._table.setItem(i, 2, QTableWidgetItem(pr.updated or pr.created or ""))
        self._update_buttons()

    def _selected_name(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _update_buttons(self):
        has_sel = self._selected_name() is not None
        self._load_btn.setEnabled(has_sel)
        self._overwrite_btn.setEnabled(has_sel and bool(self._active_ids))
        self._delete_btn.setEnabled(has_sel)

    # ── actions ────────────────────────────────────────────────────────────

    def _save_current(self):
        if not self._active_ids:
            QMessageBox.information(self, "Nothing to save",
                "No active mods in the current session. Run a scan first.")
            return
        name, ok = QInputDialog.getText(self, "Save profile",
            "Profile name:", text="My profile")
        if not ok or not name.strip():
            return
        name = name.strip()
        existing = profiles_mod.load(name)
        overwrite = False
        if existing:
            resp = QMessageBox.question(self, "Overwrite?",
                f"A profile called \"{name}\" already exists. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            overwrite = (resp == QMessageBox.StandardButton.Yes)
        pr = profiles_mod.save(name, self._active_ids, self._load_order,
                                overwrite=overwrite)
        self._refresh()
        # Select the row we just wrote
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == pr.name:
                self._table.selectRow(r)
                break

    def _load_selected(self):
        name = self._selected_name()
        if not name:
            return
        pr = profiles_mod.load(name)
        if not pr:
            QMessageBox.warning(self, "Not found", f"Profile \"{name}\" could not be read.")
            self._refresh()
            return
        resp = QMessageBox.question(self, "Load profile",
            f"Load \"{pr.name}\" ({len(pr.mod_ids)} mods)?\n\n"
            "This will overwrite modmanager-mods.txt. You'll need to restart PZ "
            "for the change to take effect.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        self.apply_requested.emit(pr.name)
        self.accept()

    def _overwrite_selected(self):
        name = self._selected_name()
        if not name or not self._active_ids:
            return
        resp = QMessageBox.question(self, "Overwrite profile",
            f"Replace \"{name}\" with the current session's {len(self._active_ids)} active mods?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        profiles_mod.save(name, self._active_ids, self._load_order, overwrite=True)
        self._refresh()

    def _delete_selected(self):
        name = self._selected_name()
        if not name:
            return
        resp = QMessageBox.question(self, "Delete profile",
            f"Delete profile \"{name}\"? This can't be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        if profiles_mod.delete(name):
            self._refresh()
        else:
            QMessageBox.warning(self, "Delete failed",
                f"Could not find or remove \"{name}\".")
