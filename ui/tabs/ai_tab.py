"""AI Assistant tab - chat with Claude/GPT about your mods, with context attachments."""
from __future__ import annotations

import html
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QKeyEvent, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import ai, config
from core.sandbox import Sandbox
from ui.style import COLOR_ACCENT, COLOR_DIM, COLOR_ERROR, COLOR_OK


@dataclass
class Attachment:
    kind: str        # "error" | "file" | "mod" | "note"
    title: str
    content: str     # what gets injected into the prompt


class ChipWidget(QFrame):
    removed = pyqtSignal(object)

    def __init__(self, att: Attachment):
        super().__init__()
        self.att = att
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            "QFrame { background: #2a2a3e; border: 1px solid #3a3a55;"
            " border-radius: 10px; padding: 2px 4px; }"
            "QLabel { background: transparent; color: #b8b8d0; font-size: 11px; }"
            "QPushButton { background: transparent; color: #888; border: none;"
            " font-weight: bold; padding: 0 4px; }"
            "QPushButton:hover { color: #f08080; }"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 4, 2)
        lay.setSpacing(4)

        icons = {"error": "!", "file": "F", "mod": "M", "note": "i"}
        ic = QLabel(f"[{icons.get(att.kind, '?')}]")
        ic.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: bold;")
        lay.addWidget(ic)

        label = QLabel(att.title)
        label.setMaximumWidth(280)
        lay.addWidget(label)

        x = QPushButton("x")
        x.setFixedSize(18, 18)
        x.clicked.connect(lambda: self.removed.emit(self))
        lay.addWidget(x)


class ConfirmRequest:
    """Shared mutable object passed through a BlockingQueuedConnection."""

    def __init__(self, path: Path, old: str, new: str):
        self.path = path
        self.old = old
        self.new = new
        self.approved: bool = False
        self.trust: bool = False


class ChatWorker(QThread):
    chunk = pyqtSignal(str)
    tool_evt = pyqtSignal(dict)        # {"name", "input", "result", "ok"}
    confirm_req = pyqtSignal(object)   # ConfirmRequest - BlockingQueued
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, provider, key, model, system, messages, sandbox):
        super().__init__()
        self.provider, self.key, self.model = provider, key, model
        self.system, self.messages = system, messages
        self.sandbox = sandbox

    def _confirmer(self, path: Path, old: str, new: str) -> tuple[bool, bool]:
        req = ConfirmRequest(path, old, new)
        self.confirm_req.emit(req)
        return req.approved, req.trust

    def run(self):
        if self.sandbox is not None and self.sandbox.confirm_write is None:
            self.sandbox.confirm_write = self._confirmer
        try:
            for event in ai.stream_chat(
                self.provider,
                self.key,
                self.model,
                self.system,
                self.messages,
                self.sandbox,
            ):
                if event["type"] == "text":
                    self.chunk.emit(event["text"])
                elif event["type"] == "tool_call":
                    self.tool_evt.emit(event)
            self.finished.emit()
        except ai.AIError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


class InputBox(QTextEdit):
    submitted = pyqtSignal()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.submitted.emit()
                return
        super().keyPressEvent(e)


class AITab(QWidget):
    def __init__(self):
        super().__init__()
        self._attachments: list[Attachment] = []
        self._chip_widgets: list[ChipWidget] = []
        self._history: list[dict] = []
        self._conversations: list[dict] = []
        self._active_conversation_id: str = ""
        self._worker: ChatWorker | None = None
        self._streaming_reply = ""
        self._readable_roots: list[Path] = []
        self._writable_roots: list[Path] = []
        self._session_trusted: bool = False
        self._session_id: str = uuid.uuid4().hex[:12]
        self._build()
        self._load_history()

    def set_file_roots(self, readable: list[Path], writable: list[Path]):
        self._readable_roots = [Path(r) for r in readable if r]
        self._writable_roots = [Path(r) for r in writable if r]

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        convo_row = QHBoxLayout()
        convo_row.setSpacing(8)
        convo_lbl = QLabel("Recents:")
        convo_lbl.setStyleSheet(f"color: {COLOR_DIM}; font-size: 11px;")
        convo_row.addWidget(convo_lbl)

        self._convo_combo = QComboBox()
        self._convo_combo.setMinimumWidth(160)
        self._convo_combo.setMaxVisibleItems(10)
        self._convo_combo.currentIndexChanged.connect(self._on_conversation_changed)
        convo_row.addWidget(self._convo_combo)

        self._new_convo_btn = QPushButton("New chat")
        self._new_convo_btn.clicked.connect(self._new_conversation)
        convo_row.addWidget(self._new_convo_btn)
        convo_row.addStretch()
        lay.addLayout(convo_row)

        self._history_view = QTextEdit()
        self._history_view.setReadOnly(True)
        self._history_view.setStyleSheet(
            "QTextEdit { background: #15151f; color: #d0d0e0;"
            " border: 1px solid #2a2a3e; border-radius: 6px;"
            " font-family: 'Segoe UI', sans-serif; font-size: 12px; padding: 10px; }"
        )
        lay.addWidget(self._history_view, stretch=1)

        self._chip_scroll = QScrollArea()
        self._chip_scroll.setWidgetResizable(True)
        self._chip_scroll.setFixedHeight(40)
        self._chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chip_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._chip_scroll.setVisible(False)

        self._chip_host = QWidget()
        self._chip_lay = QHBoxLayout(self._chip_host)
        self._chip_lay.setContentsMargins(0, 4, 0, 4)
        self._chip_lay.setSpacing(6)
        self._chip_lay.addStretch()
        self._chip_scroll.setWidget(self._chip_host)
        lay.addWidget(self._chip_scroll)

        self._input = InputBox()
        self._input.setPlaceholderText(
            "Ask about an error, request a patch, or bounce ideas...   (Ctrl+Enter to send)"
        )
        self._input.setFixedHeight(90)
        self._input.submitted.connect(self._send)
        lay.addWidget(self._input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {COLOR_DIM}; font-size: 11px;")
        btn_row.addWidget(self._status)
        btn_row.addStretch()

        self._history_btn = QPushButton("History & Revert...")
        self._history_btn.setToolTip(
            "See every file the AI has written and roll back individual or all writes."
        )
        self._history_btn.clicked.connect(self._open_history)
        btn_row.addWidget(self._history_btn)

        self._clear_btn = QPushButton("Clear chat")
        self._clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(self._clear_btn)

        self._send_btn = QPushButton("Send  >")
        self._send_btn.setObjectName("scanBtn")
        self._send_btn.clicked.connect(self._send)
        btn_row.addWidget(self._send_btn)

        lay.addLayout(btn_row)

    def add_attachment(self, att: Attachment):
        self._attachments.append(att)
        chip = ChipWidget(att)
        chip.removed.connect(self._remove_chip)
        self._chip_widgets.append(chip)
        self._chip_lay.insertWidget(self._chip_lay.count() - 1, chip)
        self._chip_scroll.setVisible(True)

    def _remove_chip(self, chip: ChipWidget):
        if chip.att in self._attachments:
            self._attachments.remove(chip.att)
        if chip in self._chip_widgets:
            self._chip_widgets.remove(chip)
        chip.setParent(None)
        chip.deleteLater()
        if not self._chip_widgets:
            self._chip_scroll.setVisible(False)

    def _clear_chips(self):
        for c in list(self._chip_widgets):
            self._remove_chip(c)

    def _effective_system_prompt(self, base: str) -> str:
        return base

    def _send(self):
        if self._worker and self._worker.isRunning():
            return

        user_text = self._input.toPlainText().strip()
        if not user_text and not self._attachments:
            return

        cfg = config.load()
        if not cfg.active_key and not ai.PROVIDERS.get(cfg.provider, {}).get("key_optional"):
            self._append_system("No API key configured. Open Settings (gear icon) to add one.")
            return

        parts: list[str] = []
        if self._attachments:
            parts.append("## Context from pzmm\n")
            for att in self._attachments:
                parts.append(f"### [{att.kind.upper()}] {att.title}\n")
                parts.append("```")
                parts.append(att.content.strip())
                parts.append("```\n")
        if user_text:
            parts.append(user_text)

        full_user = "\n".join(parts).strip()
        self._history.append({"role": "user", "content": full_user})
        self._render_message("user", full_user)
        self._clear_chips()
        self._input.clear()

        self._streaming_reply = ""
        self._append_message_header("assistant")
        tool_note = ""
        sandbox = None

        if cfg.allow_file_access:
            if not self._readable_roots:
                self._append_system(
                    "File access is enabled but no scan has run yet - click Scan first so the AI knows allowed folders."
                )
            else:
                sandbox = Sandbox(
                    readable_roots=self._readable_roots,
                    writable_roots=self._writable_roots,
                    protect_game_data=cfg.protect_game_data,
                    trusted=cfg.ai_trusted_mode or self._session_trusted,
                    confirm_write=None,
                    session_id=self._session_id,
                )
                if sandbox.has_roots():
                    flags = []
                    if cfg.ai_trusted_mode or self._session_trusted:
                        flags.append("trusted")
                    if not cfg.protect_game_data:
                        flags.append("game-data guard OFF")
                    tool_note = f"  [file tools ON{', ' + ', '.join(flags) if flags else ''}]"

        self._status.setText(f"Thinking... ({cfg.provider} / {cfg.active_model}){tool_note}")
        self._send_btn.setEnabled(False)

        self._worker = ChatWorker(
            cfg.provider,
            cfg.active_key,
            cfg.active_model,
            self._effective_system_prompt(cfg.system_prompt),
            self._history,
            sandbox,
        )
        self._worker.chunk.connect(self._on_chunk)
        self._worker.tool_evt.connect(self._on_tool_evt)
        self._worker.confirm_req.connect(
            self._on_confirm_request, Qt.ConnectionType.BlockingQueuedConnection
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_confirm_request(self, req):
        from ui.confirm_write_dialog import ConfirmWriteDialog

        dlg = ConfirmWriteDialog(req.path, req.old, req.new, self)
        dlg.exec()
        req.approved = dlg.approved
        req.trust = dlg.trust_session
        if dlg.trust_session:
            self._session_trusted = True

    def _on_chunk(self, text: str):
        self._streaming_reply += text
        self._append_plain(text)

    def _on_tool_evt(self, evt: dict):
        name = evt.get("name", "?")
        args = evt.get("input", {}) or {}
        ok = evt.get("ok", False)
        path = args.get("path", "")
        result = evt.get("result", "")

        verb = {"read_file": "read", "write_file": "WROTE", "list_dir": "listed"}.get(name, name)
        color = COLOR_OK if ok else COLOR_ERROR
        icon = "[*]" if ok else "[X]"

        first_line = result.splitlines()[0] if result else ""
        summary = first_line[:120] + ("..." if len(first_line) > 120 else "")

        self._append_html(
            f'<div style="color:{color}; font-family:Consolas,monospace; font-size:11px;'
            f' margin:4px 0; padding:4px 8px; background:#1f1f28; border-left:2px solid {color};">'
            f"{icon} {verb} <b>{html.escape(path)}</b><br>"
            f'<span style="color:{COLOR_DIM};">{html.escape(summary)}</span>'
            "</div>"
        )

    def _on_finished(self):
        self._history.append({"role": "assistant", "content": self._streaming_reply})
        self._status.setText("")
        self._send_btn.setEnabled(True)
        self._append_html("<div style='height:8px;'></div>")
        self._touch_active_conversation()
        self._persist_history()

    def _on_error(self, msg: str):
        self._status.setText("")
        self._send_btn.setEnabled(True)
        self._append_system(f"Error: {msg}")
        if self._history and self._history[-1].get("role") == "user":
            self._history.pop()

    def _append_html(self, html_text: str):
        cursor = self._history_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html_text)
        cursor.insertHtml("<br>")
        self._history_view.setTextCursor(cursor)
        self._history_view.ensureCursorVisible()

    def _append_plain(self, text: str):
        cursor = self._history_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._history_view.setTextCursor(cursor)
        self._history_view.ensureCursorVisible()

    def _render_message(self, role: str, content: str):
        self._append_message_header(role)
        content_esc = html.escape(content).replace("\n", "<br>")
        self._append_html(
            f'<div style="white-space:pre-wrap; line-height:1.35; margin:2px 0 8px 0;">{content_esc}</div>'
        )

    def _append_message_header(self, role: str):
        label = "YOU" if role == "user" else "AI"
        color = COLOR_ACCENT if role == "user" else COLOR_OK
        self._append_html(f'<div style="color:{color}; font-weight:700; margin-top:8px;">[{label}]</div>')

    def _append_system(self, msg: str):
        self._append_html(
            f'<div style="color:{COLOR_ERROR}; font-style:italic; margin:6px 0;">{html.escape(msg)}</div>'
        )

    def _flash_status(self, msg: str, ms: int = 2200):
        self._status.setStyleSheet(f"color: {COLOR_OK}; font-size: 11px; font-weight: 700;")
        self._status.setText(msg)

        def _clear():
            if self._status.text() == msg:
                self._status.setText("")
                self._status.setStyleSheet(f"color: {COLOR_DIM}; font-size: 11px;")

        QTimer.singleShot(ms, _clear)

    def _title_from_text(self, text: str) -> str:
        if not text:
            return ""
        line = text.strip().splitlines()[0]
        line = " ".join(line.split())
        if len(line) > 48:
            line = line[:45].rstrip() + "..."
        return line

    def _touch_active_conversation(self):
        now = time.time()
        for convo in self._conversations:
            if convo.get("id") == self._active_conversation_id:
                convo["updated_at"] = now
                return

    def _refresh_conversation_combo(self):
        ordered = sorted(
            self._conversations,
            key=lambda c: float(c.get("updated_at", 0.0)),
            reverse=True,
        )
        self._conversations = ordered
        self._convo_combo.blockSignals(True)
        self._convo_combo.clear()
        # Pinned first row so "new chat" is always clearly separated.
        self._convo_combo.addItem("+ New chat", "__new__")
        pick = 0
        for i, convo in enumerate(self._conversations):
            title = (convo.get("title") or "New chat").strip() or "New chat"
            cid = convo.get("id", "")
            self._convo_combo.addItem(f"Recent: {title}", cid)
            if cid == self._active_conversation_id:
                pick = i + 1
        self._convo_combo.setCurrentIndex(pick if self._convo_combo.count() else -1)
        self._convo_combo.blockSignals(False)

    def _load_history(self):
        cfg = config.load()
        convos = list(getattr(cfg, "conversation_threads", []) or [])
        if not convos:
            legacy = list(cfg.history or [])
            convos = [{
                "id": uuid.uuid4().hex[:12],
                "title": "Current chat" if legacy else "New chat",
                "updated_at": time.time(),
                "history": legacy,
            }]
        self._conversations = convos

        wanted = (getattr(cfg, "active_conversation_id", "") or "").strip()
        selected = next((c for c in self._conversations if c.get("id") == wanted), None)
        if selected is None:
            selected = sorted(
                self._conversations,
                key=lambda c: float(c.get("updated_at", 0.0)),
                reverse=True,
            )[0]

        self._active_conversation_id = selected.get("id", "")
        self._history = list(selected.get("history", []) or [])
        self._refresh_conversation_combo()

        self._history_view.clear()
        if not self._history:
            self._render_welcome()
            return
        for msg in self._history:
            self._render_message(msg.get("role", "user"), msg.get("content", ""))

    def _persist_history(self):
        self._history = self._history[-40:]
        now = time.time()

        found = False
        for convo in self._conversations:
            if convo.get("id") != self._active_conversation_id:
                continue
            convo["history"] = list(self._history)
            convo["updated_at"] = now
            if (convo.get("title") or "") in {"", "New chat", "Current chat"}:
                first_user = next(
                    (m.get("content", "") for m in self._history if m.get("role") == "user"),
                    "",
                )
                convo["title"] = self._title_from_text(first_user) or "New chat"
            found = True
            break

        if not found:
            new_id = self._active_conversation_id or uuid.uuid4().hex[:12]
            self._active_conversation_id = new_id
            self._conversations.append({
                "id": new_id,
                "title": "New chat",
                "updated_at": now,
                "history": list(self._history),
            })

        self._conversations = sorted(
            self._conversations,
            key=lambda c: float(c.get("updated_at", 0.0)),
            reverse=True,
        )[:30]

        cfg = config.load()
        cfg.conversation_threads = self._conversations
        cfg.active_conversation_id = self._active_conversation_id
        cfg.history = list(self._history)  # backward-compatible mirror
        config.save(cfg)
        self._refresh_conversation_combo()

    def _render_welcome(self):
        self._history_view.setHtml(
            f'<div style="color:{COLOR_DIM}; padding:20px;">'
            f'<b style="color:{COLOR_ACCENT};">AI Assistant</b><br><br>'
            "Chat with Claude or GPT about your mods.<br><br>"
            "Tips:<br>"
            "- Right-click any error in the <b>Errors</b> tab -> <i>Ask AI</i> to auto-attach it<br>"
            "- Right-click any mod in the <b>Mods</b> tab -> <i>Debug with AI</i> for a full bundle<br>"
            "- Add your API key in <b>Settings</b> (gear icon, top-right)<br>"
            "- Enable <i>file access</i> in Settings to let the AI read and patch mod files directly<br>"
            "- Use <b>Recents</b> above to switch between saved conversations<br>"
            "- Ctrl+Enter to send<br><br>"
            "</div>"
        )

    def _new_conversation(self):
        if self._worker and self._worker.isRunning():
            return
        self._persist_history()
        convo = {
            "id": uuid.uuid4().hex[:12],
            "title": "New chat",
            "updated_at": time.time(),
            "history": [],
        }
        self._conversations.insert(0, convo)
        self._active_conversation_id = convo["id"]
        self._history = []
        self._clear_chips()
        self._history_view.clear()
        self._render_welcome()
        self._append_html(
            f'<div style="display:block; margin:12px 0 10px 0; padding:8px 10px; border-left:3px solid {COLOR_OK};'
            f' background:#17261f; color:{COLOR_OK}; font-weight:600;">'
            "Started a new chat. Previous conversations are still in Recents."
            "</div>"
        )
        self._refresh_conversation_combo()
        self._session_id = uuid.uuid4().hex[:12]
        self._session_trusted = False
        self._persist_history()
        self._flash_status("New chat started")

    def _on_conversation_changed(self, idx: int):
        if idx < 0:
            return
        new_id = str(self._convo_combo.itemData(idx) or "")
        if new_id == "__new__":
            self._new_conversation()
            return
        if not new_id or new_id == self._active_conversation_id:
            return
        if self._worker and self._worker.isRunning():
            return

        self._persist_history()
        self._active_conversation_id = new_id
        convo = next((c for c in self._conversations if c.get("id") == new_id), None)
        self._history = list((convo or {}).get("history", []) or [])
        self._clear_chips()
        self._history_view.clear()

        if not self._history:
            self._render_welcome()
        else:
            for msg in self._history:
                self._render_message(msg.get("role", "user"), msg.get("content", ""))
        self._persist_history()

    def _clear(self):
        self._history = []
        self._clear_chips()
        self._history_view.clear()
        self._render_welcome()
        self._touch_active_conversation()
        self._persist_history()
        self._session_id = uuid.uuid4().hex[:12]
        self._session_trusted = False

    def _open_history(self):
        from ui.backups_dialog import BackupsDialog

        dlg = BackupsDialog(self, current_session=self._session_id)
        dlg.exec()
