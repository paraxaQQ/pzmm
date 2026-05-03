"""Steam Workshop browser tab."""
from __future__ import annotations

import webbrowser

from PyQt6.QtCore import QTimer, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QMessageBox, QFrame, QSizePolicy, QStyle
)

from core import steam

PZ_WORKSHOP_URL = f"https://steamcommunity.com/app/{steam.PZ_APP_ID}/workshop/"

STEAM_TOP_LEVEL_HOSTS = {
    "steamcommunity.com",
    "store.steampowered.com",
    "help.steampowered.com",
    "login.steampowered.com",
}


try:
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _HAS_WEBENGINE = True
except Exception:
    QWebEnginePage = object
    QWebEngineProfile = object
    QWebEngineView = object
    _HAS_WEBENGINE = False


def _is_allowed_top_level_url(url: QUrl) -> bool:
    scheme = (url.scheme() or "").lower()
    if scheme not in {"http", "https"}:
        return False
    host = (url.host() or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host in STEAM_TOP_LEVEL_HOSTS or host.endswith(".steamcommunity.com")


if _HAS_WEBENGINE:
    class WorkshopPage(QWebEnginePage):
        blockedNavigation = pyqtSignal(str)

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            if is_main_frame and not _is_allowed_top_level_url(url):
                self.blockedNavigation.emit(url.toString())
                return False
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)
else:
    class WorkshopPage:  # type: ignore[no-redef]
        pass


class WorkshopTab(QWidget):
    """Embedded Steam Workshop browser, locked to Steam-owned pages."""

    def __init__(self):
        super().__init__()
        self._request_rescan = None
        self._steam_timer = QTimer(self)
        self._steam_timer.setInterval(5000)
        self._steam_timer.timeout.connect(self._refresh_steam_status)
        self._build()

    def set_rescan_handler(self, fn):
        self._request_rescan = fn

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)

        self._back_btn = QPushButton("")
        self._back_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self._back_btn.setObjectName("iconBtn")
        self._back_btn.setFixedWidth(34)
        self._back_btn.setToolTip("Back")
        top.addWidget(self._back_btn)

        self._forward_btn = QPushButton("")
        self._forward_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self._forward_btn.setObjectName("iconBtn")
        self._forward_btn.setFixedWidth(34)
        self._forward_btn.setToolTip("Forward")
        top.addWidget(self._forward_btn)

        self._reload_btn = QPushButton("Reload")
        self._reload_btn.setToolTip("Reload the current Workshop page")
        top.addWidget(self._reload_btn)

        self._home_btn = QPushButton("PZ Workshop")
        self._home_btn.setToolTip("Go to the Project Zomboid Workshop")
        top.addWidget(self._home_btn)

        self._url = QLineEdit(PZ_WORKSHOP_URL)
        self._url.setObjectName("readOnlyUrl")
        self._url.setReadOnly(True)
        self._url.setToolTip("Current embedded browser URL")
        self._url.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top.addWidget(self._url, stretch=1)

        self._steam_status = QLabel("")
        self._steam_status.setMinimumWidth(118)
        top.addWidget(self._steam_status)

        self._popout_btn = QPushButton("Pop out")
        self._popout_btn.setToolTip("Open this page in your default browser")
        self._popout_btn.clicked.connect(self._popout_current)
        top.addWidget(self._popout_btn)

        self._rescan_btn = QPushButton("Rescan")
        self._rescan_btn.setToolTip("Scan again after Steam finishes downloading subscribed mods")
        self._rescan_btn.clicked.connect(self._rescan)
        top.addWidget(self._rescan_btn)

        lay.addLayout(top)

        notice = QLabel(
            "Sign in only on Steam pages. pzmm does not read, store, autofill, or persist Steam browser data."
        )
        notice.setObjectName("workshopNotice")
        notice.setWordWrap(True)
        lay.addWidget(notice)

        if not _HAS_WEBENGINE:
            fallback = self._missing_webengine_panel()
            lay.addWidget(fallback, stretch=1)
            self._set_controls_enabled(False)
            self._refresh_steam_status()
            self._steam_timer.start()
            return

        self._profile = QWebEngineProfile(self)
        self._profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self._page = WorkshopPage(self._profile, self)
        self._page.blockedNavigation.connect(self._on_blocked_navigation)

        self._view = QWebEngineView()
        self._view.setPage(self._page)
        self._view.urlChanged.connect(self._on_url_changed)
        self._view.loadFinished.connect(self._refresh_nav_buttons)
        self._view.load(QUrl(PZ_WORKSHOP_URL))

        self._back_btn.clicked.connect(self._view.back)
        self._forward_btn.clicked.connect(self._view.forward)
        self._reload_btn.clicked.connect(self._view.reload)
        self._home_btn.clicked.connect(lambda: self._view.load(QUrl(PZ_WORKSHOP_URL)))

        lay.addWidget(self._view, stretch=1)
        self._refresh_steam_status()
        self._refresh_nav_buttons()
        self._steam_timer.start()

    def _missing_webengine_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("emptyPanel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(18, 18, 18, 18)
        pl.setSpacing(10)
        title = QLabel("Embedded browser unavailable")
        title.setObjectName("heading")
        body = QLabel(
            "Install PyQt6-WebEngine to browse Steam Workshop inside pzmm. "
            "The popout button still opens the Project Zomboid Workshop externally."
        )
        body.setWordWrap(True)
        pl.addWidget(title)
        pl.addWidget(body)
        pl.addStretch()
        return panel

    def _set_controls_enabled(self, enabled: bool):
        for btn in (self._back_btn, self._forward_btn, self._reload_btn, self._home_btn):
            btn.setEnabled(enabled)

    def _refresh_steam_status(self):
        running = steam.is_steam_running()
        self._steam_status.setText("Steam running" if running else "Steam not detected")
        self._steam_status.setObjectName("ok" if running else "warn")
        self._steam_status.style().unpolish(self._steam_status)
        self._steam_status.style().polish(self._steam_status)

    def _refresh_nav_buttons(self):
        if not _HAS_WEBENGINE:
            return
        history = self._view.history()
        self._back_btn.setEnabled(history.canGoBack())
        self._forward_btn.setEnabled(history.canGoForward())

    def _on_url_changed(self, url: QUrl):
        self._url.setText(url.toString())
        self._refresh_nav_buttons()

    def _on_blocked_navigation(self, url: str):
        QMessageBox.information(
            self,
            "Navigation blocked",
            "The embedded Workshop browser is locked to Steam pages.\n\n"
            f"Blocked URL:\n{url}",
        )

    def _current_url(self) -> str:
        if _HAS_WEBENGINE and hasattr(self, "_view"):
            url = self._view.url().toString()
            if url:
                return url
        return PZ_WORKSHOP_URL

    def _popout_current(self):
        try:
            webbrowser.open(self._current_url())
        except Exception as e:
            QMessageBox.warning(self, "Pop out failed", str(e))

    def _rescan(self):
        if self._request_rescan is None:
            return
        self._request_rescan()
