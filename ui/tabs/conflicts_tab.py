"""Conflicts tab — file conflicts with detail panel."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QLabel, QLineEdit, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ui.style import COLOR_WARN, COLOR_ERROR, COLOR_DIM, COLOR_ACCENT, COLOR_OK


class ConflictsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._conflicts = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: conflict list ───────────────────────────────────────────────
        left = QWidget()
        from PyQt6.QtWidgets import QVBoxLayout as VL
        ll = VL(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter files…")
        self._search.textChanged.connect(self._filter)
        ll.addWidget(self._search)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["File", "# Mods", "Winner"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.currentItemChanged.connect(lambda cur, _: self._on_select(self._table.currentRow()))
        ll.addWidget(self._table)
        splitter.addWidget(left)

        # ── Right: detail ─────────────────────────────────────────────────────
        right = QWidget()
        rl = VL(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self._detail_lbl = QLabel("Select a conflict to see details")
        self._detail_lbl.setStyleSheet("font-weight: 700; color: #9090b0; background: transparent;")
        rl.addWidget(self._detail_lbl)

        self._detail_tree = QTreeWidget()
        self._detail_tree.setHeaderLabels(["Mod", "Load Position", "Full Path"])
        self._detail_tree.setAlternatingRowColors(True)
        self._detail_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._detail_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._detail_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        rl.addWidget(self._detail_tree)
        splitter.addWidget(right)

        splitter.setSizes([440, 500])
        lay.addWidget(splitter)

    def _cell(self, text: str, color: str | None = None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if color:
            item.setForeground(QColor(color))
        return item

    def _filter(self, text: str):
        text = text.lower()
        for row in range(self._table.rowCount()):
            val = (self._table.item(row, 0) or QTableWidgetItem("")).text().lower()
            self._table.setRowHidden(row, bool(text and text not in val))

    def _on_select(self, row: int):
        self._detail_tree.clear()
        if row < 0 or row >= len(self._conflicts):
            return
        # Find the actual conflict matching this row (sorting may reorder)
        item = self._table.item(row, 0)
        if not item:
            return
        filename = item.toolTip() or item.text()
        conflict = next((c for c in self._conflicts if c.rel_path == filename), None)
        if not conflict:
            return

        self._detail_lbl.setText(f"Conflict: {conflict.rel_path.split('/')[-1]}")

        total = len(conflict.providers)
        for i, prov in enumerate(conflict.providers):
            is_winner = prov.id == (conflict.winner.id if conflict.winner else "")
            pos = f"{i+1} of {total}" + (" ← WINS" if is_winner else "")
            node = QTreeWidgetItem([prov.name, pos, str(prov.path)])
            node.setForeground(0, QColor(COLOR_ACCENT if is_winner else COLOR_DIM))
            node.setForeground(1, QColor(COLOR_OK if is_winner else COLOR_DIM))
            node.setForeground(2, QColor(COLOR_DIM))
            self._detail_tree.addTopLevelItem(node)

    def update_results(self, scan_result: dict):
        self._conflicts = scan_result["file_conflicts"]
        self._detail_tree.clear()
        self._detail_lbl.setText("Select a conflict to see details")

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._conflicts))

        for row, fc in enumerate(self._conflicts):
            filename = fc.rel_path.split("/")[-1]
            item = self._cell(filename)
            item.setToolTip(fc.rel_path)   # store full path for lookup
            self._table.setItem(row, 0, item)
            self._table.setItem(row, 1, self._cell(str(len(fc.providers)), COLOR_WARN))
            self._table.setItem(row, 2, self._cell(
                fc.winner.name if fc.winner else "?", COLOR_ACCENT))

        self._table.setSortingEnabled(True)
