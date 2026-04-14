"""Errors tab — real runtime errors parsed from console.txt, mapped to mods."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QLineEdit, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ui.style import COLOR_ERROR, COLOR_WARN, COLOR_DIM, COLOR_ACCENT, COLOR_OK


class ErrorsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._by_mod: dict = {}
        self._visible_keys: list[str] = []
        self._entries: list = []          # entries for currently-selected mod
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter mods…")
        self._search.textChanged.connect(self._filter)
        lay.addWidget(self._search)

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
        self._detail.setHeaderLabels(["Message / Stack", "Severity", "File", "Line"])
        self._detail.setAlternatingRowColors(True)
        self._detail.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._detail.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._detail.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._detail.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._detail.currentItemChanged.connect(self._on_item_select)
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

    def _filter(self, text: str):
        text = text.lower()
        for i in range(self._mod_list.count()):
            item = self._mod_list.item(i)
            if item:
                item.setHidden(bool(text and text not in item.text().lower()))

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
            sev_color = COLOR_ERROR if e.severity == "error" else COLOR_WARN
            root = QTreeWidgetItem([
                e.message,
                e.severity.upper(),
                e.file or "",
                str(e.line) if e.line else "",
            ])
            root.setForeground(0, QColor(sev_color))
            root.setForeground(1, QColor(sev_color))
            root.setForeground(2, QColor(COLOR_DIM))
            root.setForeground(3, QColor(COLOR_DIM))
            root.setData(0, Qt.ItemDataRole.UserRole, e)   # stash entry

            for s in e.stack:
                child = QTreeWidgetItem([s, "", "", ""])
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
        if e.file:
            loc = e.file + (f":{e.line}" if e.line else "")
            lines.append(f"Location: {loc}")
        if e.stack:
            lines.append("")
            lines.append("Stack trace:")
            lines.extend(f"  {s}" for s in e.stack)

        self._fulltext.setPlainText("\n".join(lines))

    # ── data update ───────────────────────────────────────────────────────────

    def update_results(self, scan_result: dict):
        report = scan_result["console_report"]
        self._by_mod = report.by_mod
        self._mod_list.clear()
        self._detail.clear()
        self._fulltext.clear()
        self._entries = []

        keys = sorted(
            self._by_mod.keys(),
            key=lambda k: (
                -sum(1 for e in self._by_mod[k] if e.severity == "error"),
                -len(self._by_mod[k])
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
            n_err  = sum(1 for e in entries if e.severity == "error")
            n_warn = len(entries) - n_err

            parts = []
            if n_err:
                parts.append(f"{n_err}E")
            if n_warn:
                parts.append(f"{n_warn}W")
            label = f"{mod_name}  [{' '.join(parts)}]"

            item = QListWidgetItem(label)
            item.setForeground(QColor(COLOR_ERROR if n_err else COLOR_WARN))
            self._mod_list.addItem(item)
