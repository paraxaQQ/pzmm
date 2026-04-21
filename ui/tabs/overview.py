"""Overview tab — stats cards + critical issues list."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QSizePolicy,
    QPushButton, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from ui.style import COLOR_OK, COLOR_WARN, COLOR_ERROR
from core import bundle as bundle_mod


def _stat_card(value: str, label: str, color: str = "#5a8fff") -> QFrame:
    card = QFrame()
    card.setFrameShape(QFrame.Shape.StyledPanel)
    card.setObjectName("statCard")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(4)

    val_lbl = QLabel(value)
    val_lbl.setObjectName("stat_value")
    val_lbl.setStyleSheet(f"color: {color};")
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

    lbl = QLabel(label)
    lbl.setObjectName("statCardLabel")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

    lay.addWidget(val_lbl)
    lay.addWidget(lbl)
    card.setMinimumWidth(150)
    return card


def _issue_row(severity: str, text: str) -> QLabel:
    colors = {"error": COLOR_ERROR, "warn": COLOR_WARN, "info": "#5a8fff"}
    icons  = {"error": "✕", "warn": "⚠", "info": "ℹ"}
    color  = colors.get(severity, "#888")
    icon   = icons.get(severity, "•")
    lbl = QLabel(f'<span style="color:{color}; font-weight:700;">{icon}</span>  {text}')
    lbl.setStyleSheet("background: transparent; padding: 4px 0;")
    lbl.setWordWrap(True)
    return lbl


class OverviewTab(QWidget):
    def __init__(self):
        super().__init__()
        self._last_scan: dict | None = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(20)

        # Stat cards row
        self._cards_row = QHBoxLayout()
        self._cards_row.setSpacing(14)
        outer.addLayout(self._cards_row)

        # Issues section header with Export button
        issues_row = QHBoxLayout()
        issues_lbl = QLabel("Issues")
        issues_lbl.setObjectName("issuesHeading")
        issues_row.addWidget(issues_lbl)
        issues_row.addStretch()
        self._export_btn = QPushButton("Export Debug Bundle…")
        self._export_btn.setToolTip(
            "Zip up console.txt, every active mod.info, and a summary report — "
            "ready to attach to a bug report."
        )
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_bundle)
        issues_row.addWidget(self._export_btn)
        outer.addLayout(issues_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._issues_widget = QWidget()
        self._issues_layout = QVBoxLayout(self._issues_widget)
        self._issues_layout.setSpacing(2)
        self._issues_layout.setContentsMargins(0, 0, 0, 0)
        self._issues_layout.addStretch()

        scroll.setWidget(self._issues_widget)
        outer.addWidget(scroll)

        self._show_placeholder()

    def _show_placeholder(self):
        self._clear_cards()
        self._add_card("—", "MODS")
        self._add_card("—", "ERRORS")
        self._add_card("—", "WARNINGS")
        self._add_card("—", "FILE CONFLICTS")
        self._add_card("—", "DEP CYCLES")
        self._clear_issues()
        self._add_issue("info", "Click Scan to analyse your mod setup.")

    def _clear_cards(self):
        while self._cards_row.count():
            item = self._cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_card(self, value: str, label: str, color: str = "#5a8fff"):
        self._cards_row.addWidget(_stat_card(value, label, color))

    def _clear_issues(self):
        while self._issues_layout.count() > 1:   # keep stretch
            item = self._issues_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_issue(self, severity: str, text: str):
        self._issues_layout.insertWidget(self._issues_layout.count() - 1,
                                         _issue_row(severity, text))

    def _export_bundle(self):
        if not self._last_scan:
            return
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"pzmm-debug-{ts}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export debug bundle",
            default_name, "Zip archives (*.zip)"
        )
        if not path:
            return
        try:
            n_info, size = bundle_mod.build_bundle(self._last_scan, Path(path))
            QMessageBox.information(
                self, "Debug bundle",
                f"Wrote {Path(path).name}\n"
                f"  {n_info} mod.info file(s) included\n"
                f"  {size:,} bytes"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    def update_results(self, scan_result: dict):
        self._last_scan = scan_result
        self._export_btn.setEnabled(True)
        mods      = scan_result["mods"]
        file_conf = scan_result["file_conflicts"]
        dep       = scan_result["dep_graph"]
        report    = scan_result["console_report"]

        n_mods   = len(mods)
        n_file   = len(file_conf)
        n_err    = getattr(report, "error_occurrences", len(report.errors))
        n_warn   = getattr(report, "warn_occurrences", len(report.warns))
        n_cycles = len(dep.cycles)

        self._clear_cards()
        self._add_card(str(n_mods),  "MODS",            "#5a8fff")
        self._add_card(str(n_err),   "ERRORS",           COLOR_ERROR if n_err   else COLOR_OK)
        self._add_card(str(n_warn),  "WARNINGS",         COLOR_WARN  if n_warn  else COLOR_OK)
        self._add_card(str(n_file),  "FILE CONFLICTS",   COLOR_WARN  if n_file  else COLOR_OK)
        self._add_card(str(n_cycles),"DEP CYCLES",       COLOR_ERROR if n_cycles else COLOR_OK)

        self._clear_issues()

        if n_cycles:
            for cid in dep.cycles:
                m = next((x for x in mods if x.id == cid), None)
                self._add_issue("error", f"Circular dependency: {m.name if m else cid}")

        for e in report.errors[:30]:
            count = max(1, getattr(e, "occurrence_count", 1))
            suffix = f" (x{count})" if count > 1 else ""
            kind = getattr(e, "kind", "")
            ktxt = f" [{kind}]" if kind else ""
            self._add_issue("error", f"{e.mod_name} - {e.message}{suffix}{ktxt}")

        for e in report.warns[:20]:
            count = max(1, getattr(e, "occurrence_count", 1))
            suffix = f" (x{count})" if count > 1 else ""
            kind = getattr(e, "kind", "")
            ktxt = f" [{kind}]" if kind else ""
            self._add_issue("warn", f"{e.mod_name} - {e.message}{suffix}{ktxt}")

        for c in file_conf[:20]:
            names = ", ".join(p.name for p in c.providers)
            self._add_issue("warn", f"File conflict: {c.rel_path}  ({names})")

        if not (n_cycles or n_err or n_warn or n_file):
            self._add_issue("info", "No issues found. Clean setup!")
