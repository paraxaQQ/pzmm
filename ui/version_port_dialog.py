"""Dialog for porting local mod version folders."""
from __future__ import annotations

from pathlib import Path
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from core import porting


class VersionPortDialog(QDialog):
    def __init__(self, *, mod_name: str, mod_root: Path, versions: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Port Version Folder")
        self.setMinimumWidth(620)
        self.setMinimumHeight(520)
        self._mod_name = mod_name
        self._mod_root = mod_root
        self._versions = versions
        self._plan: porting.PortPlan | None = None
        self._build()
        self._refresh_preview()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        title = QLabel(
            f"<b>{self._mod_name}</b><br>"
            f"<span style='color:#888'>Root: {self._mod_root}</span>"
        )
        title.setWordWrap(True)
        lay.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)
        self._from_combo = QComboBox()
        self._from_combo.addItems(self._versions)
        if self._versions:
            self._from_combo.setCurrentIndex(len(self._versions) - 1)
        self._from_combo.currentTextChanged.connect(self._refresh_preview)
        form.addRow("From folder:", self._from_combo)

        self._to_combo = QComboBox()
        self._to_combo.setEditable(True)
        self._to_combo.addItems(self._versions)
        if self._versions:
            self._to_combo.setCurrentText(self._versions[-1])
        self._to_combo.currentTextChanged.connect(self._refresh_preview)
        form.addRow("To folder:", self._to_combo)

        folder_hint = QLabel(
            "These are versioned folder names under the mod root (not the mod.info version string)."
        )
        folder_hint.setWordWrap(True)
        folder_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", folder_hint)

        self._copy_missing_only = QCheckBox("Copy only missing files")
        self._copy_missing_only.toggled.connect(self._on_option_change)
        form.addRow("", self._copy_missing_only)

        self._overwrite = QCheckBox("Overwrite existing files")
        self._overwrite.setChecked(True)
        self._overwrite.toggled.connect(self._on_option_change)
        form.addRow("", self._overwrite)

        self._backup = QCheckBox("Create backup before overwrite")
        self._backup.setChecked(True)
        self._backup.toggled.connect(self._refresh_preview)
        form.addRow("", self._backup)

        lay.addLayout(form)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        lay.addWidget(self._summary)

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        lay.addWidget(self._preview, stretch=1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(self._run)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("Port")

    def _on_option_change(self):
        if self._copy_missing_only.isChecked():
            self._overwrite.setChecked(False)
            self._overwrite.setEnabled(False)
        else:
            self._overwrite.setEnabled(True)
        self._refresh_preview()

    def _refresh_preview(self):
        self._plan = None
        from_v = self._from_combo.currentText().strip()
        to_v = self._to_combo.currentText().strip()

        try:
            plan = porting.build_port_plan(self._mod_root, from_v, to_v)
            self._plan = plan
        except Exception as e:
            self._summary.setText(f"<span style='color:#e85050'>Preview unavailable: {e}</span>")
            self._preview.setPlainText("")
            self._ok_btn.setEnabled(False)
            return

        missing = len(plan.missing_files)
        existing = len(plan.existing_files)
        overwrite = self._overwrite.isChecked() and not self._copy_missing_only.isChecked()
        to_copy = missing + (existing if overwrite else 0)
        will_backup = overwrite and self._backup.isChecked() and plan.target_dir.exists()
        self._summary.setText(
            f"Source files: {plan.source_count} | Copy: {to_copy} | "
            f"Existing in target: {existing} | Backup: {'yes' if will_backup else 'no'}"
        )

        lines: list[str] = []
        for rel in plan.missing_files[:180]:
            lines.append(f"[COPY] {rel.as_posix()}")
        if overwrite:
            for rel in plan.existing_files[:180]:
                lines.append(f"[OVERWRITE] {rel.as_posix()}")
        else:
            for rel in plan.existing_files[:80]:
                lines.append(f"[SKIP existing] {rel.as_posix()}")
        if not lines:
            lines.append("No files would be copied with current options.")
        self._preview.setPlainText("\n".join(lines))
        self._ok_btn.setEnabled(to_copy > 0)

    def _run(self):
        if self._plan is None:
            return
        try:
            result = porting.execute_port(
                self._plan,
                copy_only_missing=self._copy_missing_only.isChecked(),
                overwrite_existing=self._overwrite.isChecked(),
                create_backup_before_overwrite=self._backup.isChecked(),
            )
        except Exception as e:
            QMessageBox.critical(self, "Port failed", str(e))
            return

        QMessageBox.information(
            self,
            "Port complete",
            f"Copied: {result.copied_files}\n"
            f"Overwritten: {result.overwritten_files}\n"
            + (f"Backup: {result.backup_path}\n" if result.backup_path else "")
            + f"Manifest: {result.manifest_path}",
        )
        self.accept()
