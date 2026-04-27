"""Main application window."""
from __future__ import annotations
import os
import webbrowser
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTabWidget, QStatusBar,
    QProgressBar, QApplication, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QFileSystemWatcher
from PyQt6.QtGui import QFont, QIcon, QFontMetrics

from ui import style
from ui.tabs.overview      import OverviewTab
from ui.tabs.mods_tab      import ModsTab
from ui.tabs.conflicts_tab import ConflictsTab
from ui.tabs.loadorder_tab import LoadOrderTab
from ui.tabs.errors_tab    import ErrorsTab
from ui.tabs.ai_tab        import AITab
from ui.settings_dialog    import SettingsDialog
from ui.profiles_dialog     import ProfilesDialog

from core import steam, mods as mods_mod, scanner, inspector, __version__ as PZMM_VERSION
from core import updates as updates_mod
from core import config as config_mod
from core import profiles as profiles_mod
from core import error_diff as error_diff_mod


class ElidedLabel(QLabel):
    """Single-line label that never paints outside its allocated width."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setText(text)

    def setText(self, text: str):
        self._full_text = text
        self.setToolTip(text)
        super().setText(self._elided_text())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        super().setText(self._elided_text())

    def _elided_text(self) -> str:
        if not self._full_text:
            return ""
        metrics = QFontMetrics(self.font())
        return metrics.elidedText(
            self._full_text,
            Qt.TextElideMode.ElideMiddle,
            max(20, self.width()),
        )


class UpdateCheckWorker(QThread):
    result = pyqtSignal(object)   # updates.UpdateInfo or None

    def run(self):
        try:
            self.result.emit(updates_mod.check_for_update())
        except Exception:
            self.result.emit(None)


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
                "dep_graph":      dep_graph,
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
        self.setWindowTitle(f"PZ Mod Manager — v{PZMM_VERSION}")
        self.resize(1280, 780)
        self.setMinimumSize(760, 520)
        self._worker: ScanWorker | None = None
        self._last_scan: dict | None = None
        self._startup_baseline_report = None
        self._console_watcher: QFileSystemWatcher | None = None
        self._console_path: str = ""
        self._console_debounce = QTimer(self)
        self._console_debounce.setSingleShot(True)
        self._console_debounce.setInterval(500)
        self._console_debounce.timeout.connect(self._refresh_errors_from_console)
        self._build()

    def _set_ai_tab_enabled(self, enabled: bool):
        idx = self._tabs.indexOf(self._tab_ai)
        if enabled:
            if idx < 0:
                self._tabs.addTab(self._tab_ai, "AI Assistant")
            return

        if idx >= 0:
            if self._tabs.currentIndex() == idx:
                self._tabs.setCurrentIndex(0)
            self._tabs.removeTab(idx)

    def _apply_runtime_settings(self, *, refresh_watch: bool = False):
        cfg = config_mod.load()
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(style.get_qss(cfg.color_theme))
        self._set_ai_tab_enabled(cfg.ai_assistant_enabled)
        self._tab_errors.set_ai_enabled(cfg.ai_assistant_enabled)
        self._tab_mods.set_ai_enabled(cfg.ai_assistant_enabled)

        if refresh_watch:
            if self._last_scan:
                self._setup_console_watch(self._last_scan)
            elif not cfg.watch_console:
                self._teardown_console_watch()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_lay = QVBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setObjectName("topToolbar")
        toolbar.setFixedHeight(52)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(16)

        title = QLabel("PZ Mod Manager")
        title.setObjectName("appTitle")
        tl.addWidget(title)

        self._path_lbl = ElidedLabel("Paths: detecting...")
        self._path_lbl.setObjectName("pathLabel")
        self._path_lbl.setMinimumWidth(0)
        self._path_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tl.addWidget(self._path_lbl, stretch=1)

        self._update_pill = QPushButton("")
        self._update_pill.setObjectName("updatePill")
        self._update_pill.setToolTip("A newer pzmm release is available — click to view it on GitHub.")
        self._update_pill.setVisible(False)
        self._update_pill.clicked.connect(self._on_update_pill)
        tl.addWidget(self._update_pill)

        self._scan_btn = QPushButton("⟳  Scan")
        self._scan_btn.setObjectName("scanBtn")
        self._scan_btn.setFixedHeight(34)
        self._scan_btn.clicked.connect(self._start_scan)
        tl.addWidget(self._scan_btn)

        self._profiles_btn = QPushButton("Profiles")
        self._profiles_btn.setFixedHeight(34)
        self._profiles_btn.setToolTip("Save or load snapshots of your active mod set")
        self._profiles_btn.clicked.connect(self._open_profiles)
        tl.addWidget(self._profiles_btn)

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setObjectName("iconBtn")
        self._settings_btn.setFixedSize(34, 34)
        self._settings_btn.setToolTip("Settings — API keys, AI model")
        self._settings_btn.clicked.connect(self._open_settings)
        tl.addWidget(self._settings_btn)

        root_lay.addWidget(toolbar)

        # Tabs
        self._tabs = QTabWidget()
        self._tab_overview  = OverviewTab()
        self._tab_mods      = ModsTab()
        self._tab_conflicts = ConflictsTab()
        self._tab_loadorder = LoadOrderTab()
        self._tab_errors    = ErrorsTab()
        self._tab_ai        = AITab()

        # Let tabs that need it push context to the AI tab
        self._tab_errors.set_ai_tab(self._tab_ai, self._tabs)
        self._tab_errors.set_baseline_reset_handler(self._reset_error_baseline)
        self._tab_mods.set_ai_tab(self._tab_ai, self._tabs)
        self._tab_mods.set_conflicts_tab(self._tab_conflicts)
        self._tab_mods.set_rescan_handler(self._start_scan)

        self._tabs.addTab(self._tab_overview,  "Overview")
        self._tabs.addTab(self._tab_mods,      "Mods")
        self._tabs.addTab(self._tab_conflicts, "Conflicts")
        self._tabs.addTab(self._tab_loadorder, "Load Order")
        self._tabs.addTab(self._tab_errors,    "Errors")
        self._tabs.addTab(self._tab_ai,        "AI Assistant")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._apply_runtime_settings(refresh_watch=False)

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

        # Update check + optional auto-scan — defer so the window paints first.
        QTimer.singleShot(250, self._post_startup)

    def _detect_paths(self):
        ws = steam.find_pz_workshop_dirs()
        lc = steam.find_local_mods_dirs()
        full_parts = []
        summary = []
        if ws:
            full_parts.append(f"Workshop: {ws[0]}")
            summary.append("Workshop")
        if lc:
            full_parts.append(f"Local: {lc[0]}")
            summary.append("Local")
        if full_parts:
            self._path_lbl.setText(f"Paths: {' + '.join(summary)}")
            self._path_lbl.setToolTip("\n".join(full_parts))
        else:
            self._path_lbl.setText("PZ not found")
            self._path_lbl.setToolTip("Project Zomboid paths were not detected.")

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
        prev_report = self._last_scan.get("console_report") if self._last_scan else None
        result = self._attach_error_diff(result, prev_report)
        self._scan_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._last_scan = result

        self._tab_overview.update_results(result)
        self._tab_mods.update_results(result)
        self._tab_conflicts.update_results(result)
        self._tab_loadorder.update_results(result)
        self._tab_errors.update_results(result)

        # Give the AI tab its sandbox roots.
        #   writable = active mod folders only
        #   readable = writable + Zomboid user folder (for logs, configs)
        from pathlib import Path
        mod_paths = [m.path for m in result.get("mods", []) if getattr(m, "path", None)]
        writable = list(mod_paths)
        readable = list(mod_paths)
        zr = result.get("zomboid_root")
        if zr and zr != "Not found":
            readable.append(Path(zr))
        self._tab_ai.set_file_roots(readable, writable)

        report = result["console_report"]
        n_mods = len(result["mods"])
        n_fc   = len(result["file_conflicts"])
        n_err  = getattr(report, "error_occurrences", len(report.errors))
        n_warn = getattr(report, "warn_occurrences", len(report.warns))
        self._status.showMessage(
            f"Scan complete — {n_mods} mods  |  {n_fc} file conflicts  |  {n_err} errors  |  {n_warn} warnings")

        self._setup_console_watch(result)

    def _on_tab_changed(self, idx: int):
        # Clear the "Errors •" flash marker once the user views the tab.
        errors_idx = self._tabs.indexOf(self._tab_errors)
        if idx == errors_idx and self._tabs.tabText(errors_idx) != "Errors":
            self._tabs.setTabText(errors_idx, "Errors")

    def _setup_console_watch(self, result: dict):
        """Watch console.txt for live updates, if enabled in settings."""
        cfg = config_mod.load()
        if not cfg.watch_console:
            self._teardown_console_watch()
            return

        zr = result.get("zomboid_root")
        if not zr or zr == "Not found":
            self._teardown_console_watch()
            return

        from pathlib import Path
        console_path = str(Path(zr) / "console.txt")
        if console_path == self._console_path and self._console_watcher is not None:
            return  # already watching this file

        self._teardown_console_watch()
        self._console_path = console_path
        self._console_watcher = QFileSystemWatcher(self)
        # Watching a not-yet-existing file is a silent no-op, so watch its
        # parent dir too — we re-add the file path once it appears.
        paths_to_watch = [str(Path(zr))]
        if Path(console_path).exists():
            paths_to_watch.append(console_path)
        self._console_watcher.addPaths(paths_to_watch)
        self._console_watcher.fileChanged.connect(self._on_console_changed)
        self._console_watcher.directoryChanged.connect(self._on_console_dir_changed)

    def _teardown_console_watch(self):
        if self._console_watcher is not None:
            try:
                self._console_watcher.deleteLater()
            except Exception:
                pass
            self._console_watcher = None
        self._console_path = ""

    def _on_console_changed(self, _path: str):
        self._console_debounce.start()

    def _on_console_dir_changed(self, _path: str):
        # console.txt may have been (re)created — re-add to the watch list.
        from pathlib import Path
        if (self._console_watcher is not None
                and self._console_path
                and Path(self._console_path).exists()
                and self._console_path not in self._console_watcher.files()):
            self._console_watcher.addPath(self._console_path)
        self._console_debounce.start()

    def _refresh_errors_from_console(self):
        if not self._last_scan or not self._console_path:
            return
        from pathlib import Path
        try:
            mods = self._last_scan.get("mods", [])
            report, _ = inspector.run_inspection(mods, Path(self._console_path))
        except Exception:
            return

        prev = self._last_scan.get("console_report")
        # Defensive: if we already had a populated report and the fresh parse
        # returned strictly fewer entries, the file was probably caught
        # mid-write. Skip this tick — we'll re-parse on the next change.
        if prev is not None:
            prev_total = (
                getattr(prev, "error_occurrences", len(prev.errors))
                + getattr(prev, "warn_occurrences", len(prev.warns))
            )
            new_total  = (
                getattr(report, "error_occurrences", len(report.errors))
                + getattr(report, "warn_occurrences", len(report.warns))
            )
            if prev_total > 0 and new_total < prev_total:
                return

        self._last_scan["console_report"] = report
        self._last_scan["error_diff"] = error_diff_mod.compute_diff(
            prev,
            report,
            self._startup_baseline_report or report,
        )
        try:
            self._tab_errors.update_results(self._last_scan)
            self._tab_overview.update_results(self._last_scan)
        except Exception:
            pass

        n_err  = getattr(report, "error_occurrences", len(report.errors))
        n_warn = getattr(report, "warn_occurrences", len(report.warns))
        d = self._last_scan.get("error_diff", {})
        inc = (((d.get("since_last") or {}).get("new_or_grew") or {}).get("occurrence_delta")) or 0
        self._status.showMessage(
            f"console.txt updated - {n_err} errors, {n_warn} warnings (+{inc} new/grown)", 5000)

        # Flash the Errors tab title when new errors come in while not viewing it.
        prev_err = getattr(prev, "error_occurrences", len(prev.errors)) if prev is not None else 0
        if prev is not None and n_err > prev_err:
            idx = self._tabs.indexOf(self._tab_errors)
            if idx >= 0 and self._tabs.currentIndex() != idx:
                self._tabs.setTabText(idx, "Errors •")

    def _attach_error_diff(self, result: dict, previous_report):
        report = result.get("console_report")
        if report is None:
            result["error_diff"] = {}
            return result
        if self._startup_baseline_report is None:
            self._startup_baseline_report = report
        result["error_diff"] = error_diff_mod.compute_diff(
            previous_report,
            report,
            self._startup_baseline_report,
        )
        return result

    def _reset_error_baseline(self) -> bool:
        if not self._last_scan:
            return False
        report = self._last_scan.get("console_report")
        if report is None:
            return False
        self._startup_baseline_report = report
        # Recompute so UI counters update immediately.
        self._last_scan["error_diff"] = error_diff_mod.compute_diff(
            report,
            report,
            self._startup_baseline_report,
        )
        try:
            self._tab_errors.update_results(self._last_scan)
        except Exception:
            pass
        self._status.showMessage("Error baseline reset to current scan.", 4000)
        return True

    def _on_error(self, tb: str):
        self._scan_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status.showMessage("Scan failed — see console for traceback")
        print(tb)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._apply_runtime_settings(refresh_watch=True)

    def _open_profiles(self):
        active_ids: list[str] = []
        load_order: list[str] = []
        if self._last_scan:
            active_ids = [m.id for m in self._last_scan.get("mods", [])]
            dep = self._last_scan.get("dep_graph")
            if dep is not None:
                # Keep only IDs that are active, preserving solver order
                active_set = set(active_ids)
                load_order = [mid for mid in dep.order if mid in active_set]
        dlg = ProfilesDialog(self,
                              current_active_ids=active_ids,
                              current_load_order=load_order or active_ids)
        dlg.apply_requested.connect(self._apply_profile)
        dlg.exec()

    def _apply_profile(self, name: str):
        pr = profiles_mod.load(name)
        if pr is None:
            QMessageBox.warning(self, "Profile missing",
                f"Could not load profile \"{name}\".")
            return
        zr = None
        if self._last_scan:
            raw = self._last_scan.get("zomboid_root")
            if raw and raw != "Not found":
                from pathlib import Path
                zr = Path(raw)
        if zr is None:
            zr = steam.find_zomboid_root()
        if zr is None:
            QMessageBox.warning(self, "Zomboid folder not found",
                "Could not locate the Zomboid user folder to write modmanager-mods.txt.")
            return
        try:
            wr = profiles_mod.apply_to_modmanager(pr, zr)
        except Exception as e:
            QMessageBox.critical(self, "Apply failed", str(e))
            return
        QMessageBox.information(self, "Profile applied",
            f"Wrote {len(pr.load_order or pr.mod_ids)} mods to:\n{wr.path}\n\n"
            + (f"Backup created: {wr.backup_path.name}\n\n" if wr.backup_path else "")
            +
            "Restart Project Zomboid for the change to take effect. "
            "Click Scan to refresh pzmm's view.")
        # Auto-rescan so the UI reflects the new active set
        self._start_scan()

    # ── Startup sequencing ───────────────────────────────────────────────────

    def _post_startup(self):
        cfg = config_mod.load()
        # Update check — always runs (silently) unless already checked recently.
        self._update_worker = UpdateCheckWorker()
        self._update_worker.result.connect(self._on_update_result)
        self._update_worker.start()
        # Optional: kick off an automatic scan
        if cfg.auto_scan_on_launch:
            self._start_scan()

    def _on_update_result(self, info):
        if info is None:
            return
        self._pending_update = info
        self._update_pill.setText(f"v{info.version} available ↗")
        self._update_pill.setVisible(True)

    def _on_update_pill(self):
        info = getattr(self, "_pending_update", None)
        if info is None:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Update available")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(
            f"<b>pzmm {info.tag}</b> is out. "
            f"You're on <b>v{PZMM_VERSION}</b>."
        )
        excerpt = (info.body or "").strip()
        if excerpt:
            if len(excerpt) > 800:
                excerpt = excerpt[:800] + "…"
            box.setInformativeText(excerpt)
        open_btn = box.addButton("Open release page", QMessageBox.ButtonRole.AcceptRole)
        dismiss  = box.addButton("Don't nag about this one", QMessageBox.ButtonRole.DestructiveRole)
        later    = box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is open_btn:
            try:
                webbrowser.open(info.url)
            except Exception:
                pass
        elif clicked is dismiss:
            updates_mod.dismiss(info.tag)
            self._update_pill.setVisible(False)


def run():
    import sys
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pzmm.desktop.app")
        except Exception:
            pass

    app = QApplication(sys.argv)
    icon = QIcon()
    try:
        # PyInstaller one-dir/one-file unpack location.
        if hasattr(sys, "_MEIPASS"):
            p = os.path.join(sys._MEIPASS, "icon.ico")  # type: ignore[attr-defined]
            if os.path.exists(p):
                icon = QIcon(p)
        # Dev/run-from-source fallback.
        if icon.isNull():
            p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.ico")
            if os.path.exists(p):
                icon = QIcon(p)
    except Exception:
        pass
    if not icon.isNull():
        app.setWindowIcon(icon)

    cfg = config_mod.load()
    app.setStyleSheet(style.get_qss(cfg.color_theme))
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    if not icon.isNull():
        win.setWindowIcon(icon)
    win.show()
    sys.exit(app.exec())
