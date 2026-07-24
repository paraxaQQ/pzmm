from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.style import COLOR_ERROR, COLOR_OK, COLOR_WARN
from ui.tabs.overview import _issue_row, _stat_card
from core import config as config_mod


class ModSecurityTab(QWidget):
    def __init__(self):
        super().__init__()
        self._last_scan: dict | None = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(20)

        self._cards_row = QHBoxLayout()
        self._cards_row.setSpacing(14)
        outer.addLayout(self._cards_row)

        issues_row = QHBoxLayout()
        issues_lbl = QLabel("Mod Security")
        issues_lbl.setObjectName("issuesHeading")
        issues_row.addWidget(issues_lbl)
        issues_row.addStretch()
        self._scan_hint = QLabel("No security scan data yet.")
        self._scan_hint.setObjectName("issuesHeading")
        self._scan_hint.setStyleSheet("color: #8b98b5;")
        issues_row.addWidget(self._scan_hint)
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
        self._add_card("—", "SCANNED MODS")
        self._add_card("—", "HIGH RISK")
        self._add_card("—", "MEDIUM RISK")
        self._add_card("—", "LOW RISK")
        self._clear_issues()
        self._add_issue("info", "Security scan not run yet. Click Scan.")

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
        self._issues_layout.insertWidget(self._issues_layout.count() - 1, _issue_row(severity, text))

    def update_results(self, scan_result: dict):
        self._last_scan = scan_result
        self._clear_cards()
        self._clear_issues()
        self._scan_hint.setText("Security scan complete.")

        cfg = config_mod.load()
        virus_enabled = bool(scan_result.get("virus_scanner_enabled", False))
        virus_results = scan_result.get("virus_scan_results", {})
        if not isinstance(virus_results, dict):
            virus_results = {}

        if not virus_enabled:
            if cfg.virus_scanning_enabled:
                self._add_card("0", "SCANNED MODS")
                self._add_card("0", "HIGH RISK")
                self._add_card("0", "MEDIUM RISK")
                self._add_card("0", "LOW RISK")
                self._add_issue("info", "Virus scanner enabled but not run in this scan.")
                return
            self._add_card("0", "SCANNED MODS")
            self._add_card("0", "HIGH RISK")
            self._add_card("0", "MEDIUM RISK")
            self._add_card("0", "LOW RISK")
            self._add_issue("warn", "Virus scanner disabled. Enable it in Settings.")
            return

        scanned_mods = 0
        n_high = 0
        n_medium = 0
        n_low = 0

        for result in virus_results.values():
            scanned_mods += 1
            risk = str(getattr(result, "risk_level", "safe")).lower()
            if risk == "high":
                n_high += 1
            elif risk == "medium":
                n_medium += 1
            elif risk == "low":
                n_low += 1

        self._add_card(str(scanned_mods), "SCANNED MODS", COLOR_OK if scanned_mods else COLOR_WARN)
        self._add_card(str(n_high), "HIGH RISK", COLOR_ERROR if n_high else COLOR_OK)
        self._add_card(str(n_medium), "MEDIUM RISK", COLOR_WARN if n_medium else COLOR_OK)
        self._add_card(str(n_low), "LOW RISK", "#8a96b3" if n_low == 0 else COLOR_OK)

        if not virus_results:
            self._add_issue("info", "Scan completed with no mods scanned.")
            return

        # Top results only; the full list is still kept in scan logs if needed.
        for mod_path, result in list(virus_results.items())[:60]:
            risk = str(getattr(result, "risk_level", "safe")).lower()
            if risk not in {"high", "medium", "low", "safe"}:
                risk = "safe"

            mod_label = str(getattr(result, "mod_id", "")) or Path(mod_path).name
            if risk == "safe":
                severity = "info"
            elif risk == "high":
                severity = "error"
            elif risk == "medium":
                severity = "warn"
            else:
                severity = "warn"

            findings = getattr(result, "findings", [])
            finding_count = len(findings) if isinstance(findings, list) else 0
            self._add_issue(
                severity,
                f"{risk.upper()}: {mod_label}  ({finding_count} findings)"
            )
