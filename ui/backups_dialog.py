"""AI write history — list every tracked write with per-item and bulk revert."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core import backups
from ui.style import COLOR_OK, COLOR_ERROR, COLOR_DIM, COLOR_WARN, COLOR_ACCENT


class BackupsDialog(QDialog):
    """Shows the backup manifest with revert controls.

    Parameters:
        current_session: session_id of the active chat, used to scope the
                         "this session only" filter. Pass "" or None if
                         there's no specific session to highlight.
    """

    def __init__(self, parent=None, current_session: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("AI write history")
        self.setMinimumSize(920, 520)
        self._current_session = current_session or ""
        self._build()
        self._reload()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)

        title = QLabel("AI write history")
        title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {COLOR_ACCENT};")
        lay.addWidget(title)

        hint = QLabel(
            "Every file the AI wrote is tracked here. Revert restores the "
            "timestamped backup for overwrites, or deletes the file for "
            "fresh creates. Backups live next to the original file as "
            "<code>.pzmm.bak-&lt;timestamp&gt;</code>."
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setStyleSheet(f"color: {COLOR_DIM}; font-size: 11px;")
        lay.addWidget(hint)

        self._only_this_session = QCheckBox("Only show writes from this chat session")
        self._only_this_session.setChecked(bool(self._current_session))
        self._only_this_session.setEnabled(bool(self._current_session))
        self._only_this_session.toggled.connect(self._reload)
        lay.addWidget(self._only_this_session)

        cols = ["Time", "Op", "Path", "Before", "After", "Status"]
        self._table = QTableWidget(0, len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        lay.addWidget(self._table, stretch=1)

        self._empty_lbl = QLabel("")
        self._empty_lbl.setStyleSheet(f"color: {COLOR_DIM}; font-style: italic;")
        lay.addWidget(self._empty_lbl)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._revert_sel = QPushButton("Revert selected")
        self._revert_sel.clicked.connect(self._revert_selected)
        btn_row.addWidget(self._revert_sel)

        self._revert_all = QPushButton("Revert ALL visible")
        self._revert_all.setToolTip("Revert every non-reverted write currently shown.")
        self._revert_all.clicked.connect(self._revert_all_visible)
        btn_row.addWidget(self._revert_all)

        btn_row.addStretch()

        self._purge = QPushButton("Purge reverted")
        self._purge.setToolTip("Remove already-reverted entries from the manifest")
        self._purge.clicked.connect(self._purge_reverted)
        btn_row.addWidget(self._purge)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)

        lay.addLayout(btn_row)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _filtered_entries(self) -> list:
        entries = backups.all_entries()
        if self._only_this_session.isChecked() and self._current_session:
            entries = [e for e in entries if e.session_id == self._current_session]
        # newest first
        return sorted(entries, key=lambda e: e.ts, reverse=True)

    def _reload(self):
        entries = self._filtered_entries()
        self._table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            t = QTableWidgetItem(e.ts)
            t.setData(Qt.ItemDataRole.UserRole, e)
            t.setForeground(QColor(COLOR_DIM))
            self._table.setItem(row, 0, t)

            op_color = COLOR_WARN if e.operation == "overwrite" else COLOR_OK
            op = QTableWidgetItem(e.operation)
            op.setForeground(QColor(op_color))
            self._table.setItem(row, 1, op)

            self._table.setItem(row, 2, QTableWidgetItem(e.path))

            self._table.setItem(row, 3, QTableWidgetItem(f"{e.size_before}"))
            self._table.setItem(row, 4, QTableWidgetItem(f"{e.size_after}"))

            if e.reverted:
                st = QTableWidgetItem("REVERTED")
                st.setForeground(QColor(COLOR_DIM))
            else:
                st = QTableWidgetItem("active")
                st.setForeground(QColor(COLOR_OK))
            self._table.setItem(row, 5, st)

        has_any = len(entries) > 0
        has_revertable = any(not e.reverted for e in entries)
        self._revert_sel.setEnabled(has_revertable)
        self._revert_all.setEnabled(has_revertable)
        if not has_any:
            self._empty_lbl.setText(
                "No AI writes on record yet. When the AI edits a file it will show up here."
            )
        else:
            self._empty_lbl.setText("")

    # ── Revert actions ────────────────────────────────────────────────────────

    def _selected_entries(self) -> list:
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        out = []
        for r in sorted(rows):
            it = self._table.item(r, 0)
            if it is None:
                continue
            e = it.data(Qt.ItemDataRole.UserRole)
            if e and not e.reverted:
                out.append(e)
        return out

    def _revert_selected(self):
        entries = self._selected_entries()
        if not entries:
            QMessageBox.information(
                self, "Revert",
                "Select one or more rows that aren't already reverted."
            )
            return
        self._confirm_and_revert(entries, "selected")

    def _revert_all_visible(self):
        entries = [e for e in self._filtered_entries() if not e.reverted]
        if not entries:
            QMessageBox.information(self, "Revert", "Nothing to revert.")
            return
        self._confirm_and_revert(entries, "all visible")

    def _confirm_and_revert(self, entries: list, label: str):
        ok = QMessageBox.question(
            self, "Revert",
            f"Revert {len(entries)} {label} write(s)?\n\n"
            "Overwrites will be rolled back from their .pzmm.bak-... copies; "
            "newly-created files will be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return

        done = 0
        failed: list[str] = []
        # Revert newest first so older overwrites (which may rely on the
        # current file existing) aren't clobbered by a later create/revert.
        for e in sorted(entries, key=lambda x: x.ts, reverse=True):
            try:
                backups.revert(e)
                done += 1
            except Exception as ex:
                failed.append(f"{e.path}: {ex}")

        self._reload()
        msg = f"Reverted {done} write(s)."
        if failed:
            msg += "\n\nFailed:\n" + "\n".join(failed[:10])
            if len(failed) > 10:
                msg += f"\n…and {len(failed) - 10} more."
        QMessageBox.information(self, "Revert complete", msg)

    def _purge_reverted(self):
        n = backups.purge_reverted()
        QMessageBox.information(
            self, "Purge",
            f"Removed {n} already-reverted entr{'y' if n == 1 else 'ies'} from the manifest."
        )
        self._reload()
