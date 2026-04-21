"""Conflicts tab - file conflicts with detail panel."""
from __future__ import annotations

import difflib
import hashlib
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QLineEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.style import COLOR_ACCENT, COLOR_DIM, COLOR_ERROR, COLOR_OK, COLOR_WARN

_MAX_DIFF_BYTES = 256 * 1024
_MAX_DIFF_LINES = 260


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

        # Left: conflict list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter files...")
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
        self._table.currentItemChanged.connect(lambda _cur, _prev: self._on_select(self._table.currentRow()))
        ll.addWidget(self._table)
        splitter.addWidget(left)

        # Right: per-provider detail + diff preview
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self._detail_lbl = QLabel("Select a conflict to see details")
        self._detail_lbl.setStyleSheet("font-weight: 700; color: #9090b0; background: transparent;")
        rl.addWidget(self._detail_lbl)

        self._detail_tree = QTreeWidget()
        self._detail_tree.setHeaderLabels(
            ["Mod", "Load Position", "Status", "File Path", "Fingerprint", "Delta vs Winner"]
        )
        self._detail_tree.setAlternatingRowColors(True)
        self._detail_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._detail_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._detail_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._detail_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._detail_tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._detail_tree.header().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._detail_tree.currentItemChanged.connect(self._on_provider_select)
        rl.addWidget(self._detail_tree)

        self._diff_lbl = QLabel("Select a provider row to see what the winner overwrites")
        self._diff_lbl.setStyleSheet("font-weight: 700; color: #9090b0; background: transparent;")
        rl.addWidget(self._diff_lbl)

        self._diff_view = QTextEdit()
        self._diff_view.setReadOnly(True)
        self._diff_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._diff_view.setStyleSheet(
            "QTextEdit { font-family: Consolas, monospace; font-size: 12px;"
            " background: #15151f; color: #c8c8dc; border: 1px solid #2a2a3e; }"
        )
        rl.addWidget(self._diff_view)

        splitter.addWidget(right)
        splitter.setSizes([500, 760])
        lay.addWidget(splitter)

    def _cell(self, text: str, color: str | None = None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if color:
            item.setForeground(QColor(color))
        return item

    def _filter(self, text: str):
        text = text.lower().strip()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            val = item.toolTip().lower() if item and item.toolTip() else (item.text().lower() if item else "")
            self._table.setRowHidden(row, bool(text and text not in val))

    @staticmethod
    def _resolve_conflict_path(mod_root: Path, rel_path: str) -> Path:
        return mod_root / Path(*rel_path.split("/"))

    @staticmethod
    def _fingerprint(path: Path) -> tuple[str, str]:
        if not path.exists() or not path.is_file():
            return "missing", ""
        try:
            data = path.read_bytes()
            digest = hashlib.sha1(data).hexdigest()
            return f"{len(data)}B | sha1:{digest[:10]}", digest
        except OSError:
            return "unreadable", ""

    @staticmethod
    def _read_text(path: Path) -> tuple[str, str]:
        if not path.exists() or not path.is_file():
            return "", "missing"
        try:
            size = path.stat().st_size
            if size > _MAX_DIFF_BYTES:
                return "", f"too large ({size} bytes)"
            return path.read_text(encoding="utf-8", errors="replace"), ""
        except OSError as e:
            return "", str(e)

    def _delta_vs_winner(self, provider_path: Path, winner_path: Path) -> str:
        ptxt, perr = self._read_text(provider_path)
        wtxt, werr = self._read_text(winner_path)
        if perr or werr:
            return "unavailable"
        if ptxt == wtxt:
            return "identical"

        add = 0
        rem = 0
        for line in difflib.unified_diff(
            ptxt.splitlines(),
            wtxt.splitlines(),
            fromfile="provider",
            tofile="winner",
            lineterm="",
        ):
            if line.startswith("+++ ") or line.startswith("--- ") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                add += 1
            elif line.startswith("-"):
                rem += 1
        return f"+{add}/-{rem} lines"

    def _build_diff_preview(self, provider_path: Path, winner_path: Path) -> str:
        ptxt, perr = self._read_text(provider_path)
        wtxt, werr = self._read_text(winner_path)
        if perr or werr:
            details = []
            if perr:
                details.append(f"provider: {perr}")
            if werr:
                details.append(f"winner: {werr}")
            return "Diff unavailable (" + ", ".join(details) + ")."
        if ptxt == wtxt:
            return "No content difference. This provider file is identical to the winner."

        diff_lines = list(
            difflib.unified_diff(
                ptxt.splitlines(),
                wtxt.splitlines(),
                fromfile=str(provider_path),
                tofile=str(winner_path),
                lineterm="",
            )
        )
        if len(diff_lines) > _MAX_DIFF_LINES:
            diff_lines = diff_lines[:_MAX_DIFF_LINES] + [
                f"... truncated to first {_MAX_DIFF_LINES} lines ..."
            ]
        return "\n".join(diff_lines)

    def _on_select(self, row: int):
        self._detail_tree.clear()
        self._diff_view.clear()
        self._diff_lbl.setText("Select a provider row to see what the winner overwrites")

        if row < 0:
            return

        # Find the actual conflict matching this row (sorting may reorder)
        item = self._table.item(row, 0)
        if not item:
            return
        rel_path = item.toolTip() or item.text()
        conflict = next((c for c in self._conflicts if c.rel_path == rel_path), None)
        if not conflict:
            return

        total = len(conflict.providers)
        winner_id = conflict.winner.id if conflict.winner else ""
        winner_path = self._resolve_conflict_path(conflict.winner.path, conflict.rel_path) if conflict.winner else None

        rows: list[tuple[int, object, Path, str, str]] = []
        hashes: set[str] = set()
        winner_hash = ""

        for i, prov in enumerate(conflict.providers):
            fpath = self._resolve_conflict_path(prov.path, conflict.rel_path)
            sig, full_hash = self._fingerprint(fpath)
            if full_hash:
                hashes.add(full_hash)
            if prov.id == winner_id:
                winner_hash = full_hash
            rows.append((i, prov, fpath, sig, full_hash))

        self._detail_lbl.setText(
            f"Conflict: {conflict.rel_path}  ({total} providers, {max(1, len(hashes))} content variants)"
        )

        for i, prov, fpath, sig, full_hash in rows:
            is_winner = prov.id == winner_id

            if sig == "missing":
                status = "MISSING"
                status_color = COLOR_ERROR
            elif sig == "unreadable":
                status = "UNREADABLE"
                status_color = COLOR_WARN
            elif is_winner:
                status = "WINS"
                status_color = COLOR_OK
            elif winner_hash and full_hash and full_hash == winner_hash:
                status = "same as winner"
                status_color = COLOR_DIM
            else:
                status = "overridden"
                status_color = COLOR_WARN

            delta = self._delta_vs_winner(fpath, winner_path) if winner_path is not None else "?"

            node = QTreeWidgetItem([
                prov.name,
                f"{i + 1} of {total}",
                status,
                str(fpath),
                sig,
                delta,
            ])
            node.setForeground(0, QColor(COLOR_ACCENT if is_winner else COLOR_DIM))
            node.setForeground(1, QColor(COLOR_DIM))
            node.setForeground(2, QColor(status_color))
            node.setForeground(3, QColor(COLOR_DIM))
            node.setForeground(4, QColor(COLOR_DIM))
            node.setForeground(5, QColor(COLOR_DIM))
            node.setData(0, Qt.ItemDataRole.UserRole, {
                "provider_name": prov.name,
                "winner_name": conflict.winner.name if conflict.winner else prov.name,
                "provider_path": str(fpath),
                "winner_path": str(winner_path) if winner_path else "",
                "is_winner": is_winner,
            })
            self._detail_tree.addTopLevelItem(node)

        if self._detail_tree.topLevelItemCount() > 0:
            self._detail_tree.setCurrentItem(self._detail_tree.topLevelItem(0))

    def _on_provider_select(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None):
        self._diff_view.clear()
        if current is None:
            self._diff_lbl.setText("Select a provider row to see what the winner overwrites")
            return

        meta = current.data(0, Qt.ItemDataRole.UserRole) or {}
        provider_name = meta.get("provider_name", "Provider")
        winner_name = meta.get("winner_name", "Winner")
        provider_path = Path(meta.get("provider_path", ""))
        winner_path = Path(meta.get("winner_path", ""))
        is_winner = bool(meta.get("is_winner", False))

        if is_winner:
            self._diff_lbl.setText(f"{provider_name} is the winner (this content overwrites others)")
            self._diff_view.setPlainText(
                "Select a non-winner row to see exactly what content this winner overwrites."
            )
            return

        self._diff_lbl.setText(f"Winner {winner_name} overwrites {provider_name}")
        self._diff_view.setPlainText(self._build_diff_preview(provider_path, winner_path))

    def update_results(self, scan_result: dict):
        self._conflicts = scan_result["file_conflicts"]
        self._detail_tree.clear()
        self._diff_view.clear()
        self._detail_lbl.setText("Select a conflict to see details")
        self._diff_lbl.setText("Select a provider row to see what the winner overwrites")

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._conflicts))

        for row, fc in enumerate(self._conflicts):
            # Show full normalized relative path so users see what is actually conflicting.
            item = self._cell(fc.rel_path)
            item.setToolTip(fc.rel_path)
            self._table.setItem(row, 0, item)
            self._table.setItem(row, 1, self._cell(str(len(fc.providers)), COLOR_WARN))
            self._table.setItem(row, 2, self._cell(fc.winner.name if fc.winner else "?", COLOR_ACCENT))

        self._table.setSortingEnabled(True)

    def focus_mod(self, mod_id: str) -> bool:
        """Focus the first visible conflict that includes `mod_id` as a provider."""
        if not mod_id:
            return False
        self._search.clear()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is None:
                continue
            rel_path = item.toolTip() or item.text()
            fc = next((c for c in self._conflicts if c.rel_path == rel_path), None)
            if fc is None:
                continue
            if any(getattr(p, "id", "") == mod_id for p in fc.providers):
                self._table.setCurrentCell(row, 0)
                self._on_select(row)
                return True
        return False
