"""Confirmation dialog shown before the AI writes a file."""
from __future__ import annotations
import difflib
import html
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton
)
from PyQt6.QtGui import QFont

from ui.style import COLOR_ACCENT, COLOR_OK, COLOR_ERROR, COLOR_DIM, COLOR_WARN


def _render_diff_html(old: str, new: str) -> str:
    """Unified diff as color-coded HTML."""
    diff = list(difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile="current",
        tofile="proposed",
        lineterm="",
    ))
    if not diff:
        return (
            f'<div style="color:{COLOR_DIM}; padding:12px;">'
            '(no textual difference — content is identical)'
            '</div>'
        )
    out = ['<pre style="font-family: Consolas, monospace; font-size: 12px;'
           ' line-height: 1.35; margin: 0;">']
    for line in diff:
        esc = html.escape(line)
        if line.startswith("+++") or line.startswith("---"):
            out.append(f'<span style="color:#888899;">{esc}</span>')
        elif line.startswith("@@"):
            out.append(f'<span style="color:{COLOR_ACCENT}; font-weight:600;">{esc}</span>')
        elif line.startswith("+"):
            out.append(f'<span style="color:#80e090; background:#0e2418;">{esc}</span>')
        elif line.startswith("-"):
            out.append(f'<span style="color:#f07070; background:#2a1010;">{esc}</span>')
        else:
            out.append(f'<span style="color:#b0b0c0;">{esc}</span>')
    out.append('</pre>')
    return "<br>".join(out)


class ConfirmWriteDialog(QDialog):
    """Modal dialog asking the user to approve a write.

    After exec(), read:
        .approved      — True if the user clicked Approve (or Approve + Trust)
        .trust_session — True if the user wants to skip future prompts this session
    """

    def __init__(self, path: Path, old: str, new: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI wants to modify a file")
        self.setMinimumSize(900, 620)
        self.approved: bool = False
        self.trust_session: bool = False
        self._build(path, old, new)

    def _build(self, path: Path, old: str, new: str):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)

        title = QLabel("AI wants to modify a file")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 800; color: {COLOR_WARN};"
        )
        lay.addWidget(title)

        path_lbl = QLabel(f"<b>File:</b>  <span style='font-family:Consolas;'>{html.escape(str(path))}</span>")
        path_lbl.setTextFormat(1)  # RichText
        path_lbl.setWordWrap(True)
        lay.addWidget(path_lbl)

        size_lbl = QLabel(
            f"<b>Before:</b> {len(old)} bytes &nbsp;&nbsp; "
            f"<b>After:</b> {len(new)} bytes "
            f"<span style='color:{COLOR_DIM};'>"
            "(a timestamped .pzmm.bak will be created before overwrite)"
            "</span>"
        )
        size_lbl.setWordWrap(True)
        lay.addWidget(size_lbl)

        diff = QTextEdit()
        diff.setReadOnly(True)
        diff.setFont(QFont("Consolas", 10))
        diff.setStyleSheet(
            "QTextEdit { background: #15151f; border: 1px solid #2a2a3e;"
            " border-radius: 6px; padding: 10px; }"
        )
        diff.setHtml(_render_diff_html(old, new))
        lay.addWidget(diff, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        deny = QPushButton("Deny")
        deny.clicked.connect(self._on_deny)
        btn_row.addWidget(deny)

        approve = QPushButton("Approve")
        approve.setDefault(True)
        approve.clicked.connect(self._on_approve)
        btn_row.addWidget(approve)

        trust = QPushButton("Approve + Trust rest of session")
        trust.clicked.connect(self._on_trust)
        btn_row.addWidget(trust)

        lay.addLayout(btn_row)

    def _on_deny(self):
        self.approved = False
        self.trust_session = False
        self.reject()

    def _on_approve(self):
        self.approved = True
        self.trust_session = False
        self.accept()

    def _on_trust(self):
        self.approved = True
        self.trust_session = True
        self.accept()
