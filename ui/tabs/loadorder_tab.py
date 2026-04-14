"""Load Order tab — topological order + dependency edges + apply button."""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QLabel, QHeaderView, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ui.style import COLOR_OK, COLOR_WARN, COLOR_ERROR, COLOR_DIM, COLOR_ACCENT


class LoadOrderTab(QWidget):
    def __init__(self):
        super().__init__()
        self._ordered_ids: list[str] = []
        self._zomboid_root: str = ""
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: solved order ────────────────────────────────────────────────
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)

        top = QHBoxLayout()
        lbl = QLabel("Suggested Load Order")
        lbl.setStyleSheet("font-weight: 700; color: #9090b0; background: transparent;")
        top.addWidget(lbl)
        top.addStretch()

        self._apply_btn = QPushButton("Apply Order")
        self._apply_btn.setToolTip("Write this load order to modmanager-mods.txt")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply_order)
        top.addWidget(self._apply_btn)
        ll.addLayout(top)

        self._order_table = QTableWidget(0, 3)
        self._order_table.setHorizontalHeaderLabels(["#", "Mod", "ID"])
        self._order_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._order_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._order_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._order_table.setAlternatingRowColors(True)
        self._order_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._order_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._order_table.verticalHeader().setVisible(False)
        ll.addWidget(self._order_table)

        splitter.addWidget(left)

        # ── Right: cycles + dep edges ─────────────────────────────────────────
        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self._cycle_lbl = QLabel("")
        self._cycle_lbl.setWordWrap(True)
        self._cycle_lbl.setStyleSheet("background: transparent;")
        rl.addWidget(self._cycle_lbl)

        lbl2 = QLabel("Dependency Edges")
        lbl2.setStyleSheet("font-weight: 700; color: #9090b0; background: transparent;")
        rl.addWidget(lbl2)

        self._dep_tree = QTreeWidget()
        self._dep_tree.setHeaderLabels(["Mod", "Requires"])
        self._dep_tree.setAlternatingRowColors(True)
        self._dep_tree.setColumnCount(2)
        self._dep_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._dep_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        rl.addWidget(self._dep_tree)

        splitter.addWidget(right)
        splitter.setSizes([480, 460])
        lay.addWidget(splitter)

    def _cell(self, text: str, color: str | None = None,
              align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        if color:
            item.setForeground(QColor(color))
        return item

    def _apply_order(self):
        if not self._ordered_ids or not self._zomboid_root:
            return
        p = Path(self._zomboid_root) / "Lua" / "modmanager-mods.txt"
        try:
            current = p.read_text(encoding="utf-8", errors="ignore")
            # Find the existing semicolon line and replace it
            lines = current.splitlines()
            new_mod_line = ";".join(self._ordered_ids)
            new_lines = []
            replaced = False
            for line in lines:
                if ";" in line and not line.startswith("VERSION"):
                    new_lines.append(new_mod_line)
                    replaced = True
                else:
                    new_lines.append(line)
            if not replaced:
                new_lines.append(new_mod_line)
            p.write_text("\n".join(new_lines), encoding="utf-8")
            QMessageBox.information(self, "Applied",
                f"Load order written to:\n{p}\n\nRestart PZ for changes to take effect.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def update_results(self, scan_result: dict):
        mods    = scan_result["mods"]
        dep     = scan_result["dep_graph"]
        self._zomboid_root = scan_result.get("zomboid_root", "")
        by_id   = {m.id: m for m in mods}

        # Deduplicate order list (solver may return dupes if graph had dupes)
        seen = set()
        deduped_order = []
        for mid in dep.order:
            if mid not in seen:
                seen.add(mid)
                deduped_order.append(mid)

        self._ordered_ids = deduped_order

        # ── Ordered list ──────────────────────────────────────────────────────
        self._order_table.setRowCount(len(deduped_order))
        for i, mid in enumerate(deduped_order):
            mod = by_id.get(mid)
            self._order_table.setItem(i, 0, self._cell(str(i + 1), COLOR_DIM,
                                                        Qt.AlignmentFlag.AlignHCenter))
            self._order_table.setItem(i, 1, self._cell(mod.name if mod else mid))
            self._order_table.setItem(i, 2, self._cell(mid, COLOR_DIM))

        self._apply_btn.setEnabled(bool(self._ordered_ids and self._zomboid_root))

        # ── Cycles ────────────────────────────────────────────────────────────
        if dep.cycles:
            names = ", ".join(by_id[c].name if c in by_id else c for c in dep.cycles)
            self._cycle_lbl.setText(
                f'<span style="color:#e85050; font-weight:700;">⚠ Circular dependencies:</span> {names}')
        else:
            self._cycle_lbl.setText(
                f'<span style="color:#40c060;">✓ No circular dependencies</span>')

        # ── Dep edges — one row per mod, children = its deps ─────────────────
        self._dep_tree.clear()
        for mod in mods:
            deps = dep.edges.get(mod.id, [])
            if not deps:
                continue
            root = QTreeWidgetItem(self._dep_tree)
            root.setText(0, mod.name)
            root.setForeground(0, QColor(COLOR_ACCENT))

            for dep_id in deps:
                dep_mod = by_id.get(dep_id)
                child = QTreeWidgetItem(root)
                child.setText(1, dep_mod.name if dep_mod else dep_id)
                child.setForeground(1, QColor(COLOR_DIM))

            root.setExpanded(True)
