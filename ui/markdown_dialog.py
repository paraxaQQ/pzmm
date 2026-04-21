"""Simple modal viewer for local markdown docs."""
from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from ui.style import COLOR_DIM


class MarkdownDialog(QDialog):
    def __init__(self, title: str, markdown_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(860, 640)
        self._build(markdown_path)

    def _build(self, markdown_path: Path) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        path_lbl = QLabel(f"Source: {markdown_path}")
        path_lbl.setWordWrap(True)
        path_lbl.setStyleSheet(f"color: {COLOR_DIM}; font-size: 11px;")
        lay.addWidget(path_lbl)

        viewer = QTextBrowser()
        viewer.setOpenExternalLinks(True)
        viewer.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        viewer.setStyleSheet(
            "QTextBrowser { background: #1a1a2e; color: #d2d2e4; border: 1px solid #333355; padding: 8px; }"
        )
        lay.addWidget(viewer, stretch=1)

        if markdown_path.exists():
            try:
                viewer.setMarkdown(markdown_path.read_text(encoding="utf-8"))
            except Exception as e:
                viewer.setPlainText(
                    "Could not read markdown file.\n\n"
                    f"Path: {markdown_path}\n"
                    f"Error: {e}"
                )
        else:
            viewer.setPlainText(
                "Markdown file not found.\n\n"
                f"Path: {markdown_path}"
            )

        viewer.moveCursor(QTextCursor.MoveOperation.Start)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self.setWindowModality(Qt.WindowModality.ApplicationModal)
