"""Application stylesheet."""

QSS = """
QMainWindow, QDialog {
    background: #16161a;
}

QWidget {
    background: #16161a;
    color: #e0e0e8;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

/* ── Tab bar ── */
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

/* ── Tables ── */
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

/* ── Tree ── */
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

/* ── Splitter ── */
QSplitter::handle {
    background: #2e2e38;
    width: 2px;
    height: 2px;
}

/* ── Scroll bars ── */
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

/* ── Buttons ── */
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

/* Scan button stands out */
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

/* ── Search / line edit ── */
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

/* ── Labels ── */
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

/* ── Status bar ── */
QStatusBar {
    background: #111116;
    color: #666680;
    border-top: 1px solid #2a2a38;
    font-size: 12px;
}
QStatusBar::item { border: none; }

/* ── Progress bar ── */
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

/* ── Combo / group box ── */
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

/* ── Tool tips ── */
QToolTip {
    background: #25253a;
    color: #e0e0f0;
    border: 1px solid #4a4a6a;
    padding: 4px 8px;
    border-radius: 4px;
}
"""

# Severity colours for table cells (use setForeground)
COLOR_OK     = "#40c060"
COLOR_WARN   = "#e8a020"
COLOR_ERROR  = "#e85050"
COLOR_DIM    = "#666688"
COLOR_ACCENT = "#5a8fff"
