"""Application stylesheet + theme helpers."""

from __future__ import annotations


THEME_OPTIONS: list[tuple[str, str]] = [
    ("Default", "midnight"),
    ("Gray", "graphite"),
    ("Red", "crimson"),
    ("Green", "verdant"),
    ("Amber", "amber"),
]


_BASE_QSS = """
QMainWindow, QDialog {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #16161a, stop:1 #111116);
}

QWidget {
    background: #16161a;
    color: #e0e0e8;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

/* Tab bar */
QTabWidget::pane {
    border: 1px solid #2e2e38;
    border-top: none;
    background: #1c1c22;
}
QTabBar::tab {
    background: #1c1c22;
    color: #888899;
    padding: 8px 22px;
    border: 1px solid #2e2e38;
    border-bottom: none;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: #25253a;
    color: #e0e0e8;
    border-bottom: 2px solid #5a8fff;
}
QTabBar::tab:hover:!selected {
    background: #20202c;
    color: #c0c0d0;
}

/* Tables */
QTableWidget, QTableView {
    background: #1c1c22;
    gridline-color: #2a2a34;
    border: 1px solid #2e2e38;
    border-radius: 4px;
    selection-background-color: #2e3a5e;
    selection-color: #e0e0f0;
    alternate-background-color: #1f1f28;
}
QTableWidget::item, QTableView::item {
    padding: 4px 8px;
    border: none;
}
QHeaderView::section {
    background: #25253a;
    color: #a0a0c0;
    border: none;
    border-right: 1px solid #2e2e38;
    border-bottom: 1px solid #2e2e38;
    padding: 6px 8px;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Tree */
QTreeWidget {
    background: #1c1c22;
    border: 1px solid #2e2e38;
    border-radius: 4px;
    alternate-background-color: #1f1f28;
    selection-background-color: #2e3a5e;
}
QTreeWidget::item {
    padding: 3px 4px;
}
QTreeWidget::item:selected {
    background: #2e3a5e;
    color: #e0e0f0;
}
QTreeWidget::branch:has-children:closed {
    image: url(none);
}

/* Splitter */
QSplitter::handle {
    background: #2e2e38;
    width: 2px;
    height: 2px;
}

/* Scroll bars */
QScrollBar:vertical {
    background: #1c1c22;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #3a3a50;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #5a5a78;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #1c1c22;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #3a3a50;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #5a5a78; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* Buttons */
QPushButton {
    background: #2e3a5e;
    color: #c0d0ff;
    border: 1px solid #3a4a78;
    border-radius: 5px;
    padding: 7px 20px;
    font-weight: 600;
}
QPushButton:hover {
    background: #3a4a78;
    border-color: #5a8fff;
}
QPushButton:pressed {
    background: #253060;
}
QPushButton:disabled {
    background: #22222a;
    color: #555568;
    border-color: #2a2a38;
}

/* Gear / icon button */
QPushButton#iconBtn {
    background: #22222e;
    color: #c0d0ff;
    border: 1px solid #3a3a50;
    border-radius: 5px;
    padding: 0;
    font-size: 18px;
    font-weight: normal;
}
QPushButton#iconBtn:hover {
    background: #2e3a5e;
    border-color: #5a8fff;
    color: #ffffff;
}
QPushButton#iconBtn:pressed {
    background: #253060;
}

/* Scan button */
QPushButton#scanBtn {
    background: #1a4a2a;
    color: #60e890;
    border-color: #2a6a3a;
    padding: 8px 28px;
    font-size: 14px;
}
QPushButton#scanBtn:hover {
    background: #1e5a32;
    border-color: #40c060;
}

/* Search / line edit */
QLineEdit {
    background: #22222e;
    border: 1px solid #3a3a50;
    border-radius: 4px;
    padding: 5px 10px;
    color: #e0e0e8;
}
QLineEdit:focus {
    border-color: #5a8fff;
}

/* Labels */
QLabel {
    background: transparent;
}
QLabel#heading {
    font-size: 15px;
    font-weight: 700;
    color: #c0c0e0;
}
QLabel#stat_value {
    font-size: 28px;
    font-weight: 700;
    color: #5a8fff;
}
QLabel#stat_label {
    font-size: 11px;
    color: #666688;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel#warn {
    color: #e8a020;
}
QLabel#error {
    color: #e85050;
}
QLabel#ok {
    color: #40c060;
}

/* Status bar */
QStatusBar {
    background: #111116;
    color: #666680;
    border-top: 1px solid #2a2a38;
    font-size: 12px;
}
QStatusBar::item { border: none; }

/* Progress bar */
QProgressBar {
    background: #22222e;
    border: 1px solid #2e2e3e;
    border-radius: 4px;
    text-align: center;
    color: #888;
    max-height: 14px;
    font-size: 11px;
}
QProgressBar::chunk {
    background: #2e6a3e;
    border-radius: 3px;
}

/* Combo / group box */
QGroupBox {
    border: 1px solid #2e2e40;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 6px;
    color: #7070a0;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}

/* Tool tips */
QToolTip {
    background: #25253a;
    color: #e0e0f0;
    border: 1px solid #4a4a6a;
    padding: 4px 8px;
    border-radius: 4px;
}

/* Top toolbar + custom labels/buttons */
QWidget#topToolbar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #111116, stop:1 #16161a);
    border-bottom: 1px solid #2a2a38;
}
QLabel#appTitle {
    font-size: 16px;
    font-weight: 800;
    color: #c0d0ff;
    background: transparent;
    letter-spacing: 0.5px;
}
QLabel#pathLabel {
    font-size: 11px;
    color: #666688;
    background: transparent;
}
QPushButton#updatePill {
    background: #2a3d5c;
    color: #c0d0ff;
    border: 1px solid #4a6d9c;
    border-radius: 14px;
    padding: 4px 12px;
    font-weight: 600;
}
QPushButton#updatePill:hover {
    background: #3a5080;
}

/* Overview cards */
QFrame#statCard {
    background: #1e1e2a;
    border: 1px solid #2e2e40;
    border-radius: 8px;
}
QLabel#statCardLabel {
    font-size: 11px;
    color: #666688;
    text-transform: uppercase;
    letter-spacing: 1px;
    background: transparent;
}
QLabel#issuesHeading {
    font-size: 13px;
    font-weight: 700;
    color: #9090b0;
    background: transparent;
}
"""


_GRAPHITE_REMAP: dict[str, str] = {
    "#16161a": "#151617",
    "#1c1c22": "#1c1d1f",
    "#25253a": "#282a2d",
    "#2e2e38": "#363a3f",
    "#20202c": "#212326",
    "#1f1f28": "#202225",
    "#22222e": "#23262a",
    "#2a2a34": "#303338",
    "#2a2a38": "#32363b",
    "#3a3a50": "#4a5058",
    "#5a5a78": "#666d78",
    "#111116": "#0f1011",
    "#666688": "#7a7f88",
    "#666680": "#777d85",
    "#555568": "#676d76",
    "#7070a0": "#868d98",
    "#1e1e2a": "#202328",
    "#2e2e40": "#383d45",
    "#9090b0": "#9ba2ad",
    "#444466": "#616874",
    "#1b1c28": "#1f2329",
    "#2f3550": "#3c444f",
    "#c8d6ff": "#d2d7df",
    "#9fb4ff": "#aab0ba",
    "#151925": "#1a1f26",
    "#272f45": "#333c48",
    "#67708c": "#7b8492",
    "#131824": "#181d24",
    "#6f7995": "#87909e",
    "#2a334a": "#364150",
    "#66708a": "#7b8593",
    "#d8e2ff": "#d9dde4",
    "#7e88a8": "#8f97a4",
    "#d7e3ff": "#d6dce5",
    "#8d98ba": "#9aa3b0",
    "#cfd8f8": "#cfd5dd",
    "#f0b34e": "#d2ad73",
    "#8a7650": "#81725a",
    "#c9d2ee": "#c8ced8",
}

_CRIMSON_REMAP: dict[str, str] = {
    "#16161a": "#0f0b0c",
    "#1c1c22": "#150d10",
    "#25253a": "#1e1116",
    "#2e2e38": "#2e1620",
    "#20202c": "#1a0f13",
    "#1f1f28": "#190e12",
    "#22222e": "#1c1014",
    "#2a2a34": "#26141b",
    "#2a2a38": "#2a151d",
    "#3a3a50": "#4d1b2a",
    "#5a5a78": "#782338",
    "#111116": "#090607",
    "#666688": "#a45669",
    "#666680": "#9e5767",
    "#555568": "#824758",
    "#7070a0": "#c26078",
    "#5a8fff": "#ff3b63",
    "#40c060": "#59cf72",
    "#e85050": "#ff4058",
    "#e8a020": "#ffb243",
    "#1e1e2a": "#1b1015",
    "#2e2e40": "#341721",
    "#9090b0": "#d26a83",
    "#444466": "#8a3c50",
    "#1b1c28": "#190f14",
    "#2f3550": "#3f1824",
    "#c8d6ff": "#ffd0dc",
    "#9fb4ff": "#ff5d82",
    "#151925": "#140c10",
    "#272f45": "#31141e",
    "#67708c": "#bc5f76",
    "#131824": "#120a0e",
    "#6f7995": "#cb6881",
    "#2a334a": "#3e1824",
    "#66708a": "#b85f75",
    "#d8e2ff": "#ffd6e1",
    "#7e88a8": "#cb6b84",
    "#d7e3ff": "#ffd6e1",
    "#8d98ba": "#cf6f88",
    "#cfd8f8": "#ffbfd0",
    "#f0b34e": "#ffb452",
    "#8a7650": "#ad865a",
    "#c9d2ee": "#f7b5c8",
}

_VERDANT_REMAP: dict[str, str] = {
    "#16161a": "#0f1511",
    "#1c1c22": "#152018",
    "#25253a": "#1a2a22",
    "#2e2e38": "#224033",
    "#20202c": "#17241c",
    "#1f1f28": "#16221a",
    "#22222e": "#18261d",
    "#2a2a34": "#213226",
    "#2a2a38": "#254031",
    "#3a3a50": "#2d5b45",
    "#5a5a78": "#3f7d5e",
    "#111116": "#0b120d",
    "#666688": "#7ca08a",
    "#666680": "#789a86",
    "#555568": "#678472",
    "#7070a0": "#87b69c",
    "#5a8fff": "#41d18a",
    "#40c060": "#56e78f",
    "#e85050": "#ff6f66",
    "#e8a020": "#f5c04f",
    "#1e1e2a": "#17241b",
    "#2e2e40": "#2d4b3a",
    "#9090b0": "#95b8a2",
    "#444466": "#62806d",
    "#1b1c28": "#152219",
    "#2f3550": "#2a4a39",
    "#c8d6ff": "#caecd8",
    "#9fb4ff": "#58df99",
    "#151925": "#131f17",
    "#272f45": "#284334",
    "#67708c": "#88ac95",
    "#131824": "#111d16",
    "#6f7995": "#95ba9f",
    "#2a334a": "#2a4838",
    "#66708a": "#86aa93",
    "#d8e2ff": "#d6f3e0",
    "#7e88a8": "#8fb89c",
    "#d7e3ff": "#d5f2e0",
    "#8d98ba": "#95c1a4",
    "#cfd8f8": "#c6e8d4",
    "#f0b34e": "#e9c060",
    "#8a7650": "#96825d",
    "#c9d2ee": "#c6e6d2",
}

_AMBER_REMAP: dict[str, str] = {
    "#16161a": "#18140f",
    "#1c1c22": "#211a13",
    "#25253a": "#2b2117",
    "#2e2e38": "#3a2c1d",
    "#20202c": "#251c14",
    "#1f1f28": "#231b14",
    "#22222e": "#271e16",
    "#2a2a34": "#30251a",
    "#2a2a38": "#382b1d",
    "#3a3a50": "#5f4425",
    "#5a5a78": "#876036",
    "#111116": "#120e0a",
    "#666688": "#a38a66",
    "#666680": "#9d855f",
    "#555568": "#7f6a4d",
    "#7070a0": "#c3a471",
    "#5a8fff": "#ffb347",
    "#40c060": "#7fd068",
    "#e85050": "#ff7a52",
    "#e8a020": "#ffc04d",
    "#1e1e2a": "#2a2016",
    "#2e2e40": "#4d3924",
    "#9090b0": "#c5a37a",
    "#444466": "#8f7557",
    "#1b1c28": "#261d14",
    "#2f3550": "#5b4329",
    "#c8d6ff": "#f7d8a5",
    "#9fb4ff": "#ffbe5a",
    "#151925": "#21190f",
    "#272f45": "#4c3722",
    "#67708c": "#bf9768",
    "#131824": "#1d150d",
    "#6f7995": "#c8a070",
    "#2a334a": "#5b4328",
    "#66708a": "#be9768",
    "#d8e2ff": "#ffe2b4",
    "#7e88a8": "#cb9f6a",
    "#d7e3ff": "#ffe1b3",
    "#8d98ba": "#d2aa74",
    "#cfd8f8": "#f3ce96",
    "#f0b34e": "#ffc25a",
    "#8a7650": "#a58a60",
    "#c9d2ee": "#e9c58d",
}


def _normalize_theme(theme: str | None) -> str:
    if not theme:
        return "midnight"
    key = theme.strip().lower()
    return key if key in {"midnight", "graphite", "crimson", "verdant", "amber"} else "midnight"


def get_qss(theme: str | None) -> str:
    key = _normalize_theme(theme)
    return remap_qss(_BASE_QSS, key)


def remap_qss(qss_text: str, theme: str | None) -> str:
    key = _normalize_theme(theme)
    remap = {
        "graphite": _GRAPHITE_REMAP,
        "crimson": _CRIMSON_REMAP,
        "verdant": _VERDANT_REMAP,
        "amber": _AMBER_REMAP,
    }.get(key)
    if remap is None:
        return qss_text
    qss = qss_text
    for old, new in remap.items():
        qss = qss.replace(old, new)
    return qss


# Back-compat constant for existing imports.
QSS = get_qss("midnight")

# Severity colours for table cells (use setForeground)
COLOR_OK     = "#40c060"
COLOR_WARN   = "#e8a020"
COLOR_ERROR  = "#e85050"
COLOR_DIM    = "#666688"
COLOR_ACCENT = "#5a8fff"
