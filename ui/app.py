"""Main application window."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTabWidget, QStatusBar,
    QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from ui.style import QSS
from ui.tabs.overview      import OverviewTab
from ui.tabs.mods_tab      import ModsTab
from ui.tabs.conflicts_tab import ConflictsTab
from ui.tabs.loadorder_tab import LoadOrderTab
from ui.tabs.errors_tab    import ErrorsTab

from core import steam, mods as mods_mod, scanner, inspector


class ScanWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit("Detecting Steam libraries…")
            workshop_dirs = steam.find_pz_workshop_dirs()
            local_dirs    = steam.find_local_mods_dirs()
            zomboid_root  = steam.find_zomboid_root()

            self.progress.emit("Loading workshop mods…")
            ws_mods = mods_mod.load_workshop_mods(workshop_dirs)

            self.progress.emit("Loading local mods…")
            lc_mods = mods_mod.load_local_mods(local_dirs)

            all_mods = ws_mods + lc_mods

            self.progress.emit("Loading active mod list…")
            active_ids = mods_mod.load_active_mod_ids(zomboid_root)
            if active_ids:
                active = [m for m in all_mods if m.id in active_ids]
                id_order = {mid: i for i, mid in enumerate(active_ids)}
                active.sort(key=lambda m: id_order.get(m.id, 99999))
            else:
                active = all_mods

            self.progress.emit(f"Scanning file conflicts across {len(active)} mods…")
            file_conflicts = scanner.scan_file_conflicts(active)

            self.progress.emit("Solving load order…")
            dep_graph = scanner.solve_load_order(active)

            self.progress.emit("Parsing console log for errors…")
            console_path = (zomboid_root / "console.txt") if zomboid_root else None
            report, _ = inspector.run_inspection(active, console_path)

            self.finished.emit({
                "mods":           active,
                "all_mods":       all_mods,
                "file_conflicts": file_conflicts,
                "func_conflicts": [],
                "dep_graph":      dep_graph,
                "analyses":       [],
                "console_report": report,
                "workshop_dirs":  [str(d) for d in workshop_dirs],
                "local_dirs":     [str(d) for d in local_dirs],
                "zomboid_root":   str(zomboid_root) if zomboid_root else "Not found",
            })
        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PZ Mod Manager")
        self.resize(1280, 780)
        self.setMinimumSize(900, 600)
        self._worker: ScanWorker | None = None
        self._build()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_lay = QVBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background: #111116; border-bottom: 1px solid #2a2a38;")
        toolbar.setFixedHeight(52)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(16)

        title = QLabel("PZ Mod Manager")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #c0d0ff; background: transparent; letter-spacing: 0.5px;")
        tl.addWidget(title)
        tl.addStretch()

        self._path_lbl = QLabel("Paths: detecting…")
        self._path_lbl.setStyleSheet("font-size: 11px; color: #444466; background: transparent;")
        tl.addWidget(self._path_lbl)

        self._scan_btn = QPushButton("⟳  Scan")
        self._scan_btn.setObjectName("scanBtn")
        self._scan_btn.setFixedHeight(34)
        self._scan_btn.clicked.connect(self._start_scan)
        tl.addWidget(self._scan_btn)

        root_lay.addWidget(toolbar)

        # Tabs
        self._tabs = QTabWidget()
        self._tab_overview  = OverviewTab()
        self._tab_mods      = ModsTab()
        self._tab_conflicts = ConflictsTab()
        self._tab_loadorder = LoadOrderTab()
        self._tab_errors    = ErrorsTab()

        self._tabs.addTab(self._tab_overview,  "Overview")
        self._tabs.addTab(self._tab_mods,      "Mods")
        self._tabs.addTab(self._tab_conflicts, "Conflicts")
        self._tabs.addTab(self._tab_loadorder, "Load Order")
        self._tabs.addTab(self._tab_errors,    "Errors")

        root_lay.addWidget(self._tabs)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(180)
        self._progress.setVisible(False)
        self._status.addPermanentWidget(self._progress)

        self._status.showMessage("Ready — click Scan to analyse your mod setup.")
        self._detect_paths()

    def _detect_paths(self):
        ws = steam.find_pz_workshop_dirs()
        lc = steam.find_local_mods_dirs()
        parts = []
        if ws:
            parts.append(f"Workshop: {ws[0]}")
        if lc:
            parts.append(f"Local: {lc[0]}")
        self._path_lbl.setText("  |  ".join(parts) if parts else "PZ not found")

    def _start_scan(self):
        if self._worker and self._worker.isRunning():
            return
        self._scan_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.showMessage("Scanning…")
        self._worker = ScanWorker()
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status.showMessage(msg)

    def _on_finished(self, result: dict):
        self._scan_btn.setEnabled(True)
        self._progress.setVisible(False)

        self._tab_overview.update_results(result)
        self._tab_mods.update_results(result)
        self._tab_conflicts.update_results(result)
        self._tab_loadorder.update_results(result)
        self._tab_errors.update_results(result)

        report = result["console_report"]
        n_mods = len(result["mods"])
        n_fc   = len(result["file_conflicts"])
        n_err  = len(report.errors)
        n_warn = len(report.warns)
        self._status.showMessage(
            f"Scan complete — {n_mods} mods  |  {n_fc} file conflicts  |  {n_err} errors  |  {n_warn} warnings")

    def _on_error(self, tb: str):
        self._scan_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status.showMessage("Scan failed — see console for traceback")
        print(tb)


def run():
    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
