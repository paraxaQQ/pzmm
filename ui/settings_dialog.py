"""Settings dialog - AI, safety, display, and scan behavior."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QTextEdit, QFormLayout, QCheckBox, QFileDialog,
    QGroupBox, QScrollArea, QWidget, QFrame, QMessageBox
)
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtCore import Qt

from core import config
from ui import style


class NoWheelComboBox(QComboBox):
    """Combo box that ignores mouse wheel changes."""

    def wheelEvent(self, event):
        event.ignore()


ANTHROPIC_MODELS = [
    # Claude 4.6 (latest)
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    # Claude 4.5
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    # Claude 3.5
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    # Claude 3
    "claude-3-opus-latest",
]

OPENAI_MODELS = [
    # GPT-5 family
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    # GPT-4.1 family
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    # GPT-4o family
    "gpt-4o",
    "gpt-4o-mini",
    # o-series reasoning
    "o4-mini",
    "o3",
    "o3-mini",
    "o1",
    "o1-mini",
    "o1-pro",
    # Older but still around
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(640)
        self.setMinimumHeight(700)
        self._cfg = config.load()
        self._orig_theme = self._cfg.color_theme or "midnight"
        self._initial_state: dict[str, object] = {}
        self._bypass_unsaved_guard = False
        self._ai_controls: list[object] = []
        self._build()

    def _mark_ai_controls(self, *widgets):
        self._ai_controls.extend(widgets)

    def _build(self):
        self._dialog_qss = """
            QGroupBox {
                background: #1b1c28;
                border: 1px solid #2f3550;
                border-radius: 10px;
                margin-top: 16px;
                padding: 14px;
                font-weight: 700;
                color: #c8d6ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #9fb4ff;
            }
            QGroupBox:disabled {
                background: #151925;
                border: 1px solid #272f45;
                color: #67708c;
            }
            QGroupBox[aiLocked="true"] {
                background: #151925;
                border: 1px solid #272f45;
                color: #67708c;
            }
            QGroupBox::title:disabled {
                color: #67708c;
            }
            QGroupBox[aiLocked="true"]::title {
                color: #67708c;
            }
            QLineEdit:disabled, QComboBox:disabled, QTextEdit:disabled {
                background: #131824;
                color: #6f7995;
                border: 1px solid #2a334a;
            }
            QLabel:disabled {
                color: #66708a;
            }
            QCheckBox:disabled {
                color: #66708a;
            }
            """
        self._apply_dialog_theme(self._orig_theme)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        header = QLabel("Settings")
        header.setStyleSheet("font-size: 19px; font-weight: 800; color: #d8e2ff;")
        root.addWidget(header)

        sub = QLabel("Configure assistant behavior, safety gates, and app appearance.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #7e88a8; font-size: 11px;")
        root.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        root.addWidget(scroll, stretch=1)

        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)
        scroll.setWidget(body)

        # AI master
        ai_master_group = QGroupBox("AI Assistant")
        ai_master_layout = QVBoxLayout(ai_master_group)
        ai_master_layout.setSpacing(8)

        self._ai_enabled = QCheckBox("Enable AI Assistant")
        self._ai_enabled.setChecked(self._cfg.ai_assistant_enabled)
        self._ai_enabled.setStyleSheet("QCheckBox { font-size: 14px; font-weight: 700; color: #d7e3ff; }")
        self._ai_enabled.toggled.connect(self._refresh_ai_enabled)
        ai_master_layout.addWidget(self._ai_enabled)

        ai_hint = QLabel(
            "When disabled, the AI tab is hidden and all provider/file-access controls stay locked."
        )
        ai_hint.setWordWrap(True)
        ai_hint.setStyleSheet("color: #7e88a8; font-size: 11px;")
        ai_master_layout.addWidget(ai_hint)
        content.addWidget(ai_master_group)

        # Provider and prompt
        self._provider_group = QGroupBox("Provider and Prompt")
        provider_layout = QVBoxLayout(self._provider_group)
        provider_layout.setSpacing(10)

        privacy = QLabel(
            "Keys are stored locally in %APPDATA%/pzmm/config.json. "
            "Requests go only to your selected provider."
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet("color: #7e88a8; font-size: 11px;")
        provider_layout.addWidget(privacy)

        self._provider_locked_hint = QLabel(
            "Locked: turn on AI Assistant above to edit provider, keys, and prompt."
        )
        self._provider_locked_hint.setWordWrap(True)
        self._provider_locked_hint.setStyleSheet("color: #8d98ba; font-size: 11px;")
        provider_layout.addWidget(self._provider_locked_hint)

        form = QFormLayout()
        form.setSpacing(10)

        self._provider = QComboBox()
        self._provider.addItems(["Anthropic (Claude)", "OpenAI (GPT)"])
        self._provider.setCurrentIndex(0 if self._cfg.provider == "anthropic" else 1)
        self._provider.currentIndexChanged.connect(self._on_provider_change)
        form.addRow("Provider:", self._provider)

        self._anthropic_key = QLineEdit(self._cfg.anthropic_key)
        self._anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._anthropic_key.setPlaceholderText("sk-ant-...")
        self._anthropic_key_label = QLabel("Anthropic key:")
        form.addRow(self._anthropic_key_label, self._anthropic_key)

        self._openai_key = QLineEdit(self._cfg.openai_key)
        self._openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_key.setPlaceholderText("sk-...")
        self._openai_key_label = QLabel("OpenAI key:")
        form.addRow(self._openai_key_label, self._openai_key)

        self._anthropic_model = QComboBox()
        self._anthropic_model.setEditable(True)
        self._anthropic_model.addItems(ANTHROPIC_MODELS)
        if self._cfg.anthropic_model not in ANTHROPIC_MODELS:
            self._anthropic_model.addItem(self._cfg.anthropic_model)
        self._anthropic_model.setCurrentText(self._cfg.anthropic_model)
        self._anthropic_model_label = QLabel("Claude model:")
        form.addRow(self._anthropic_model_label, self._anthropic_model)

        self._openai_model = QComboBox()
        self._openai_model.setEditable(True)
        self._openai_model.addItems(OPENAI_MODELS)
        if self._cfg.openai_model not in OPENAI_MODELS:
            self._openai_model.addItem(self._cfg.openai_model)
        self._openai_model.setCurrentText(self._cfg.openai_model)
        self._openai_model_label = QLabel("GPT model:")
        form.addRow(self._openai_model_label, self._openai_model)
        provider_layout.addLayout(form)

        sys_label = QLabel("System prompt")
        sys_label.setStyleSheet(
            "QLabel { color: #cfd8f8; font-weight: 600; }"
            "QLabel:disabled { color: #66708a; }"
        )
        provider_layout.addWidget(sys_label)

        self._sysprompt = QTextEdit()
        self._sysprompt.setPlainText(self._cfg.system_prompt)
        self._sysprompt.setMinimumHeight(130)
        provider_layout.addWidget(self._sysprompt)
        content.addWidget(self._provider_group)

        self._mark_ai_controls(
            self._provider_group,
            self._provider,
            self._anthropic_key,
            self._openai_key,
            self._anthropic_model,
            self._openai_model,
            self._anthropic_key_label,
            self._openai_key_label,
            self._anthropic_model_label,
            self._openai_model_label,
            sys_label,
            self._sysprompt,
        )

        # File access and safety
        self._access_group = QGroupBox("File Access and Safety")
        access_layout = QVBoxLayout(self._access_group)
        access_layout.setSpacing(8)

        self._file_access = QCheckBox(
            "By clicking this box you allow your AI of choice to modify your game files"
        )
        self._file_access.setChecked(self._cfg.allow_file_access)
        self._file_access.setStyleSheet(
            "QCheckBox { color: #f0b34e; font-weight: 700; }"
            "QCheckBox:disabled { color: #8a7650; }"
        )
        self._file_access.toggled.connect(self._refresh_file_toggles)
        access_layout.addWidget(self._file_access)

        hint = QLabel(
            "When enabled, AI can read your mod folders + Zomboid user folder, and write only to mod folders. "
            "Writes create .pzmm.bak backups and prompt for approval unless trusted mode is on."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #7e88a8; font-size: 11px;")
        access_layout.addWidget(hint)

        self._access_locked_hint = QLabel(
            "Locked: enable AI Assistant first, then enable file access to unlock write controls."
        )
        self._access_locked_hint.setWordWrap(True)
        self._access_locked_hint.setStyleSheet("color: #8d98ba; font-size: 11px;")
        access_layout.addWidget(self._access_locked_hint)

        self._trusted_mode = QCheckBox("Trusted mode - skip per-write approval")
        self._trusted_mode.setChecked(self._cfg.ai_trusted_mode)
        self._trusted_mode.setStyleSheet(
            "QCheckBox { color: #c9d2ee; padding-left: 16px; }"
            "QCheckBox:disabled { color: #66708a; }"
        )
        access_layout.addWidget(self._trusted_mode)

        self._protect_game_data = QCheckBox(
            "Protect game data - refuse writes under Saves / Sandbox Presets / ActiveMods"
        )
        self._protect_game_data.setChecked(self._cfg.protect_game_data)
        self._protect_game_data.setStyleSheet(
            "QCheckBox { color: #c9d2ee; padding-left: 16px; }"
            "QCheckBox:disabled { color: #66708a; }"
        )
        access_layout.addWidget(self._protect_game_data)

        content.addWidget(self._access_group)
        self._mark_ai_controls(self._access_group, self._file_access, hint, self._trusted_mode, self._protect_game_data)

        # Appearance
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setSpacing(10)

        self._theme = NoWheelComboBox()
        for label, key in style.THEME_OPTIONS:
            self._theme.addItem(label, key)
        idx = self._theme.findData(self._cfg.color_theme)
        if idx < 0:
            idx = 0
        self._theme.setCurrentIndex(idx)
        self._theme.currentIndexChanged.connect(self._preview_theme)
        appearance_layout.addRow("Color theme:", self._theme)
        content.addWidget(appearance_group)

        # Tools
        tools_group = QGroupBox("Tools")
        tools_layout = QVBoxLayout(tools_group)
        tools_layout.setSpacing(8)

        editor_label = QLabel("External editor")
        editor_label.setStyleSheet("color: #cfd8f8; font-weight: 600;")
        tools_layout.addWidget(editor_label)

        editor_row = QHBoxLayout()
        self._editor_cmd = QLineEdit(self._cfg.external_editor)
        self._editor_cmd.setPlaceholderText(
            r"Leave blank to auto-detect (Notepad++ -> Notepad on Windows)"
        )
        editor_row.addWidget(self._editor_cmd, stretch=1)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._pick_editor)
        editor_row.addWidget(browse)
        tools_layout.addLayout(editor_row)
        content.addWidget(tools_group)

        # Scanning
        scan_group = QGroupBox("Scanning")
        scan_layout = QVBoxLayout(scan_group)
        scan_layout.setSpacing(6)

        self._auto_scan = QCheckBox("Scan automatically on launch")
        self._auto_scan.setChecked(self._cfg.auto_scan_on_launch)
        scan_layout.addWidget(self._auto_scan)

        self._watch_console = QCheckBox("Watch console.txt for changes (live-refresh Errors tab)")
        self._watch_console.setChecked(self._cfg.watch_console)
        scan_layout.addWidget(self._watch_console)

        content.addWidget(scan_group)
        content.addStretch(1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self._cancel_without_save)
        save = QPushButton("Save")
        save.setDefault(True)
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        root.addLayout(btn_row)

        self._refresh_ai_enabled(self._ai_enabled.isChecked())
        self._initial_state = self._collect_state()

    def _repolish(self, widget):
        style_obj = widget.style()
        if style_obj:
            style_obj.unpolish(widget)
            style_obj.polish(widget)
        widget.update()

    def _refresh_ai_enabled(self, on: bool):
        for w in self._ai_controls:
            w.setEnabled(on)
        self._provider_locked_hint.setVisible(not on)
        self._access_locked_hint.setVisible(not on)
        self._provider_group.setProperty("aiLocked", not on)
        self._access_group.setProperty("aiLocked", not on)
        self._repolish(self._provider_group)
        self._repolish(self._access_group)
        self._on_provider_change(self._provider.currentIndex())
        self._refresh_file_toggles(on and self._file_access.isChecked())

    def _refresh_file_toggles(self, on: bool):
        self._trusted_mode.setEnabled(on)
        self._protect_game_data.setEnabled(on)
        ai_on = self._ai_enabled.isChecked()
        self._access_locked_hint.setVisible(not ai_on or not on)

    def _on_provider_change(self, idx: int):
        anthropic_active = (idx == 0)
        ai_on = self._ai_enabled.isChecked()

        self._provider.setEnabled(ai_on)
        self._anthropic_key.setEnabled(ai_on and anthropic_active)
        self._anthropic_model.setEnabled(ai_on and anthropic_active)
        self._openai_key.setEnabled(ai_on and not anthropic_active)
        self._openai_model.setEnabled(ai_on and not anthropic_active)

        self._anthropic_key_label.setStyleSheet(
            "" if ai_on and anthropic_active else f"color: {style.COLOR_DIM};"
        )
        self._anthropic_model_label.setStyleSheet(
            "" if ai_on and anthropic_active else f"color: {style.COLOR_DIM};"
        )
        self._openai_key_label.setStyleSheet(
            "" if ai_on and not anthropic_active else f"color: {style.COLOR_DIM};"
        )
        self._openai_model_label.setStyleSheet(
            "" if ai_on and not anthropic_active else f"color: {style.COLOR_DIM};"
        )

    def _pick_editor(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick external editor",
            "", "Executables (*.exe);;All files (*)"
        )
        if path:
            self._editor_cmd.setText(path)

    def _preview_theme(self):
        app = QApplication.instance()
        key = str(self._theme.currentData() or "midnight")
        if app is not None:
            app.setStyleSheet(style.get_qss(key))
        self._apply_dialog_theme(key)

    def _cancel_without_save(self):
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(style.get_qss(self._orig_theme))
        self._apply_dialog_theme(self._orig_theme)
        self._bypass_unsaved_guard = True
        self.reject()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_without_save()
            event.accept()
            return
        super().keyPressEvent(event)

    def reject(self):
        if self._bypass_unsaved_guard:
            super().reject()
            return
        if not self._attempt_force_save():
            return
        super().reject()

    def _apply_dialog_theme(self, theme_key: str):
        self.setStyleSheet(style.remap_qss(self._dialog_qss, theme_key))

    def closeEvent(self, event):
        if self._bypass_unsaved_guard:
            event.accept()
            return
        if self._attempt_force_save():
            event.accept()
        else:
            event.ignore()

    def _collect_state(self) -> dict[str, object]:
        return {
            "ai_assistant_enabled": self._ai_enabled.isChecked(),
            "provider": self._provider.currentIndex(),
            "anthropic_key": self._anthropic_key.text().strip(),
            "openai_key": self._openai_key.text().strip(),
            "anthropic_model": self._anthropic_model.currentText().strip(),
            "openai_model": self._openai_model.currentText().strip(),
            "system_prompt": self._sysprompt.toPlainText().strip(),
            "allow_file_access": self._file_access.isChecked(),
            "ai_trusted_mode": self._trusted_mode.isChecked(),
            "protect_game_data": self._protect_game_data.isChecked(),
            "color_theme": str(self._theme.currentData() or "midnight"),
            "external_editor": self._editor_cmd.text().strip(),
            "auto_scan_on_launch": self._auto_scan.isChecked(),
            "watch_console": self._watch_console.isChecked(),
        }

    def _is_dirty(self) -> bool:
        return self._collect_state() != self._initial_state

    def _attempt_force_save(self) -> bool:
        if not self._is_dirty():
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(style.get_qss(self._orig_theme))
            self._apply_dialog_theme(self._orig_theme)
            return True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved changes")
        box.setText("Your changes aren't saved.")
        box.setInformativeText("Save your changes before closing Settings.")
        save_btn = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        keep_btn = box.addButton("Keep editing", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.exec()

        if box.clickedButton() is keep_btn:
            return False

        self._save()
        return False  # _save() closes the dialog

    def _save(self):
        self._cfg.ai_assistant_enabled = self._ai_enabled.isChecked()
        self._cfg.provider = "anthropic" if self._provider.currentIndex() == 0 else "openai"
        self._cfg.anthropic_key = self._anthropic_key.text().strip()
        self._cfg.openai_key = self._openai_key.text().strip()
        self._cfg.anthropic_model = self._anthropic_model.currentText().strip()
        self._cfg.openai_model = self._openai_model.currentText().strip()
        self._cfg.system_prompt = self._sysprompt.toPlainText().strip()
        self._cfg.allow_file_access = self._file_access.isChecked()
        self._cfg.ai_trusted_mode = self._trusted_mode.isChecked()
        self._cfg.protect_game_data = self._protect_game_data.isChecked()
        self._cfg.color_theme = str(self._theme.currentData() or "midnight")
        self._cfg.external_editor = self._editor_cmd.text().strip()
        self._cfg.auto_scan_on_launch = self._auto_scan.isChecked()
        self._cfg.watch_console = self._watch_console.isChecked()
        config.save(self._cfg)
        self._initial_state = self._collect_state()
        self._orig_theme = self._cfg.color_theme or "midnight"
        self._bypass_unsaved_guard = True
        self.accept()
