"""B41 Inspector tab — per-mod Lua compatibility issues."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QTextEdit, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from ui.style import COLOR_OK, COLOR_WARN, COLOR_ERROR, COLOR_DIM, COLOR_ACCENT


class InspectorTab(QWidget):
    def __init__(self):
        super().__init__()
        self._analyses = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter mods…")
        self._search.textChanged.connect(self._filter)
        lay.addWidget(self._search)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: mod list ranked by hit count ───────────────────────────────
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)

        self._mod_list = QListWidget()
        self._mod_list.currentRowChanged.connect(self._on_mod_select)
        ll.addWidget(self._mod_list)
        splitter.addWidget(left)

        # ── Right: hit detail tree ────────────────────────────────────────────
        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)

        self._detail = QTreeWidget()
        self._detail.setHeaderLabels(["File / API", "Kind", "Line", "Reason"])
        self._detail.setAlternatingRowColors(True)
        self._detail.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._detail.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._detail.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._detail.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        rl.addWidget(self._detail)

        splitter.addWidget(right)
        splitter.setSizes([300, 640])
        lay.addWidget(splitter)

    def _filter(self, text: str):
        text = text.lower()
        for i in range(self._mod_list.count()):
            item = self._mod_list.item(i)
            if item:
                item.setHidden(bool(text and text not in item.text().lower()))

    def _on_mod_select(self, row: int):
        self._detail.clear()
        if row < 0 or row >= len(self._visible_analyses):
            return
        ma = self._visible_analyses[row]

        # Group hits by file
        file_map: dict[str, list] = {}
        for path, hit in ma.all_b41_hits:
            key = str(path)
            file_map.setdefault(key, []).append((path, hit))

        for fpath, hits in file_map.items():
            file_root = QTreeWidgetItem([fpath.split("/")[-1].split("\\")[-1], "", "", ""])
            file_root.setForeground(0, QColor(COLOR_ACCENT))
            file_root.setToolTip(0, fpath)

            for _, hit in sorted(hits, key=lambda x: x[1].line):
                child = QTreeWidgetItem([
                    hit.api,
                    hit.kind,
                    str(hit.line),
                    hit.reason,
                ])
                child.setForeground(0, QColor(COLOR_ERROR))
                child.setForeground(1, QColor(COLOR_DIM))
                child.setForeground(2, QColor(COLOR_DIM))
                child.setForeground(3, QColor(COLOR_WARN))
                file_root.addChild(child)

            self._detail.addTopLevelItem(file_root)
            file_root.setExpanded(True)

    def update_results(self, scan_result: dict):
        analyses = scan_result["analyses"]

        # Sort: mods with hits first, ranked by hit count descending
        self._analyses = sorted(
            analyses,
            key=lambda ma: -len(ma.all_b41_hits)
        )
        self._visible_analyses = self._analyses[:]

        self._mod_list.clear()
        self._detail.clear()

        for ma in self._analyses:
            n = len(ma.all_b41_hits)
            text = f"{ma.mod.name}  [{n} hit{'s' if n != 1 else ''}]" if n else ma.mod.name
            item = QListWidgetItem(text)
            if n > 0:
                item.setForeground(QColor(COLOR_ERROR))
            else:
                item.setForeground(QColor(COLOR_DIM))
            self._mod_list.addItem(item)
