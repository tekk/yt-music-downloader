"""Modern Dark Mode Stylesheet and Typography configuration for PyQt6 GUI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from PyQt6.QtGui import QFont, QFontDatabase, QIcon

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).parent / "fonts"
ICONS_DIR = Path(__file__).parent / "icons"


def get_app_icon_path() -> Path:
    """Return the filesystem path to the main application icon PNG."""
    main_icon = ICONS_DIR / "icon.png"
    if main_icon.exists():
        return main_icon
    # Fallback to packaging or img directory if running from source tree
    repo_icon = Path(__file__).resolve().parent.parent.parent / "packaging" / "yt-music-downloader.png"
    if repo_icon.exists():
        return repo_icon
    return main_icon


def get_app_icon() -> QIcon:
    """Load and return the main application QIcon with all bundled resolutions."""
    icon = QIcon()
    if ICONS_DIR.exists():
        # Add available resolution sizes for pixel-perfect rendering across display densities
        for size in (16, 24, 32, 48, 64, 128, 256, 512):
            size_path = ICONS_DIR / f"icon_{size}.png"
            if size_path.exists():
                icon.addFile(str(size_path))

        # Also add master icon.png and icon.ico if present
        main_png = ICONS_DIR / "icon.png"
        if main_png.exists():
            icon.addFile(str(main_png))
        ico_path = ICONS_DIR / "icon.ico"
        if ico_path.exists():
            icon.addFile(str(ico_path))

    if icon.isNull():
        fallback = get_app_icon_path()
        if fallback.exists():
            icon = QIcon(str(fallback))

    return icon


def load_application_fonts() -> Dict[str, str]:
    """Register bundled modern TTF fonts (Montserrat, Roboto, JetBrains Mono) with Qt."""
    loaded_families: Dict[str, str] = {
        "title": "Montserrat",
        "body": "Roboto",
        "mono": "JetBrains Mono",
    }

    if not FONTS_DIR.exists():
        logger.warning("Fonts directory not found at %s", FONTS_DIR)
        return loaded_families

    for font_file in FONTS_DIR.glob("*.ttf"):
        try:
            font_id = QFontDatabase.addApplicationFont(str(font_file))
            if font_id == -1:
                logger.warning("Failed to load font: %s", font_file.name)
        except Exception as e:
            logger.warning("Error loading font %s: %e", font_file.name, e)

    return loaded_families


DARK_THEME_QSS = """
/* Global Reset & Base */
QWidget {
    background-color: #121212;
    color: #E0E0E0;
    font-family: 'Roboto', 'Segoe UI', sans-serif;
    font-size: 13px;
    selection-background-color: #FF0033;
    selection-color: #FFFFFF;
}

/* Card Container Panels */
QFrame#card-frame, QWidget#card {
    background-color: #1A1A1A;
    border: 1px solid #2B2B2B;
    border-radius: 10px;
}

/* Headings and Titles */
QLabel#app-title {
    font-family: 'Montserrat', 'Segoe UI', sans-serif;
    font-size: 20px;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 0.5px;
}

QLabel#section-title {
    font-family: 'Montserrat', 'Segoe UI', sans-serif;
    font-size: 14px;
    font-weight: 700;
    color: #00E5FF;
    margin-bottom: 4px;
}

QLabel#status-banner {
    font-family: 'Roboto', sans-serif;
    font-size: 13px;
    color: #B3B3B3;
}

/* Inputs & Text Fields */
QLineEdit {
    background-color: #242424;
    color: #FFFFFF;
    border: 1px solid #383838;
    border-radius: 8px;
    padding: 8px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1.5px solid #00E5FF;
    background-color: #282828;
}

/* Dropdowns / Select Boxes */
QComboBox {
    background-color: #242424;
    color: #FFFFFF;
    border: 1px solid #383838;
    border-radius: 8px;
    padding: 7px 12px;
    font-family: 'Roboto', sans-serif;
    min-width: 140px;
}

QComboBox:focus {
    border: 1.5px solid #00E5FF;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left: none;
}

QComboBox QAbstractItemView {
    background-color: #202020;
    color: #FFFFFF;
    border: 1px solid #383838;
    border-radius: 6px;
    selection-background-color: #FF0033;
    padding: 4px;
}

/* Standard Buttons */
QPushButton {
    background-color: #262626;
    color: #FFFFFF;
    border: 1px solid #3A3A3A;
    border-radius: 8px;
    padding: 8px 16px;
    font-family: 'Roboto', sans-serif;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #333333;
    border-color: #555555;
}

QPushButton:pressed {
    background-color: #1C1C1C;
}

QPushButton:disabled {
    background-color: #1A1A1A;
    color: #555555;
    border-color: #282828;
}

/* Primary Action Buttons */
QPushButton#btn-download {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF0033, stop:1 #E6002E);
    color: #FFFFFF;
    border: none;
    font-family: 'Montserrat', sans-serif;
    font-weight: 800;
    font-size: 13px;
    letter-spacing: 0.5px;
    padding: 9px 24px;
}

QPushButton#btn-download:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF1A47, stop:1 #FF0033);
}

QPushButton#btn-inspect {
    background-color: #00B4D8;
    color: #000000;
    border: none;
    font-family: 'Montserrat', sans-serif;
    font-weight: 700;
}

QPushButton#btn-inspect:hover {
    background-color: #00E5FF;
}

QPushButton#btn-cancel {
    background-color: #331A1A;
    color: #FF5252;
    border: 1px solid #FF5252;
    font-weight: 700;
}

QPushButton#btn-cancel:hover {
    background-color: #4A1A1A;
}

QPushButton#btn-liked-songs {
    background-color: #241C22;
    color: #FF4081;
    border: 1px solid #FF4081;
    font-family: 'Montserrat', sans-serif;
    font-weight: 700;
}

QPushButton#btn-liked-songs:hover {
    background-color: #381C2E;
}

QPushButton#btn-my-playlists {
    background-color: #16242B;
    color: #00E5FF;
    border: 1px solid #00E5FF;
    font-family: 'Montserrat', sans-serif;
    font-weight: 700;
}

QPushButton#btn-my-playlists:hover {
    background-color: #1C333D;
}

/* Auth Pill Badge */
QPushButton#auth-badge {
    border-radius: 14px;
    padding: 4px 14px;
    font-family: 'Roboto', sans-serif;
    font-size: 12px;
    font-weight: bold;
}

QPushButton#auth-badge[authenticated="true"] {
    background-color: #143320;
    color: #00E676;
    border: 1px solid #00E676;
}

QPushButton#auth-badge[authenticated="false"] {
    background-color: #332B14;
    color: #FFB300;
    border: 1px solid #FFB300;
}

/* Table View */
QTableWidget {
    background-color: #181818;
    alternate-background-color: #1F1F1F;
    gridline-color: #2B2B2B;
    border: 1px solid #2B2B2B;
    border-radius: 8px;
    font-family: 'Roboto', sans-serif;
}

QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #252525;
}

QTableWidget::item:selected {
    background-color: #331A22;
    color: #FFFFFF;
}

QHeaderView::section {
    background-color: #222222;
    color: #00E5FF;
    font-family: 'Montserrat', sans-serif;
    font-weight: 700;
    font-size: 12px;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #333333;
}

/* Progress Bars */
QProgressBar {
    background-color: #242424;
    border: 1px solid #333333;
    border-radius: 7px;
    height: 14px;
    text-align: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: bold;
    color: #FFFFFF;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF0033, stop:1 #FF5252);
    border-radius: 6px;
}

QProgressBar#overall-bar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00B4D8, stop:1 #00E5FF);
    border-radius: 6px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #2B2B2B;
    border-radius: 8px;
    background-color: #1A1A1A;
    top: -1px;
}

QTabBar::tab {
    background-color: #222222;
    color: #A0A0A0;
    font-family: 'Montserrat', sans-serif;
    font-weight: 600;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #1A1A1A;
    color: #FFFFFF;
    border-bottom: 2px solid #FF0033;
}

QTabBar::tab:hover:!selected {
    background-color: #2A2A2A;
    color: #E0E0E0;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: #141414;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #383838;
    min-height: 25px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #555555;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #141414;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #383838;
    min-width: 25px;
    border-radius: 5px;
}

/* Activity Log Console */
QPlainTextEdit#log-console {
    background-color: #0E0E0E;
    color: #A5D6A7;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    border: 1px solid #2B2B2B;
    border-radius: 8px;
    padding: 8px;
}
"""
