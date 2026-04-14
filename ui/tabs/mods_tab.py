"""Mods tab — searchable table of all scanned mods."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QTableWidget, QTableWidgetItem, QLabel, QHeaderView
)
from PyQt6.QtCore import Qt, QSortFilterProxyModel
from PyQt6.QtGui import QColor
from ui.style import COLOR_OK, COLOR_WARN, COLOR_ERROR, COLOR_DIM


class ModsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Search bar
        top = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search mods…")
        self._search.textChanged.connect(self._filter)
        top.addWidget(self._search)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #555570; font-size: 12px; background: transparent;")
        top.addWidget(self._count_lbl)
        lay.addLayout(top)

        # Table
        cols = ["Name", "ID", "Source", "PZ Ver", "Errors", "File Conflicts", "Status"]
        self._table = QTableWidget(0, len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        lay.addWidget(self._table)

        self._rows: list[dict] = []

    def _filter(self, text: str):
        text = text.lower()
        for row in range(self._table.rowCount()):
            name = (self._table.item(row, 0) or QTableWidgetItem("")).text().lower()
            mid  = (self._table.item(row, 1) or QTableWidgetItem("")).text().lower()
            hide = bool(text and text not in name and text not in mid)
            self._table.setRowHidden(row, hide)
        visible = sum(
            1 for r in range(self._table.rowCount())
            if not self._table.isRowHidden(r)
        )
        self._count_lbl.setText(f"{visible} of {self._table.rowCount()} mods")

    def _cell(self, text: str, color: str | None = None, align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        if color:
            item.setForeground(QColor(color))
        return item

    def update_results(self, scan_result: dict):
        mods      = scan_result["mods"]
        file_conf = scan_result["file_conflicts"]
        report    = scan_result["console_report"]

        # Map mod name (lowered, stripped) → error/warn count from console
        err_map:  dict[str, int] = {}
        warn_map: dict[str, int] = {}
        for e in report.errors:
            err_map[e.mod_id] = err_map.get(e.mod_id, 0) + 1
        for e in report.warns:
            warn_map[e.mod_id] = warn_map.get(e.mod_id, 0) + 1

        # Map mod id → file conflict count
        fc_map: dict[str, int] = {}
        for fc in file_conf:
            for prov in fc.providers:
                fc_map[prov.id] = fc_map.get(prov.id, 0) + 1

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(mods))

        for row, mod in enumerate(mods):
            mod_key = mod.id.lower().replace(" ", "").replace("'", "")
            n_err  = err_map.get(mod_key, 0)
            n_warn = warn_map.get(mod_key, 0)
            fc     = fc_map.get(mod.id, 0)

            if n_err > 0:
                status, scol = "ERRORS",    COLOR_ERROR
            elif n_warn > 0:
                status, scol = "WARNINGS",  COLOR_WARN
            elif fc > 0:
                status, scol = "CONFLICTS", COLOR_WARN
            else:
                status, scol = "OK",        COLOR_OK

            err_str  = str(n_err)  if n_err  else "—"
            warn_str = str(n_warn) if n_warn else "—"
            fc_str   = str(fc)     if fc     else "—"

            self._table.setItem(row, 0, self._cell(mod.name))
            self._table.setItem(row, 1, self._cell(mod.id, COLOR_DIM))
            self._table.setItem(row, 2, self._cell(mod.source, COLOR_DIM))
            self._table.setItem(row, 3, self._cell(mod.pz_version, COLOR_DIM))
            self._table.setItem(row, 4, self._cell(err_str,
                                                    COLOR_ERROR if n_err else COLOR_DIM,
                                                    Qt.AlignmentFlag.AlignHCenter))
            self._table.setItem(row, 5, self._cell(fc_str,
                                                    COLOR_WARN if fc else COLOR_DIM,
                                                    Qt.AlignmentFlag.AlignHCenter))
            self._table.setItem(row, 6, self._cell(status, scol, Qt.AlignmentFlag.AlignHCenter))

        self._table.setSortingEnabled(True)
        self._count_lbl.setText(f"{len(mods)} mods")
        self._filter(self._search.text())
