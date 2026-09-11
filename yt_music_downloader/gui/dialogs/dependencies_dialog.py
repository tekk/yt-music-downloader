"""Dependencies inspection modal dialog for PyQt6 desktop GUI."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...dependencies import check_all_dependencies, get_ffmpeg_install_guide, get_os_info


class DependenciesDialog(QDialog):
    """Modal dialog displaying system external dependencies status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Dependencies & External Tools")
        self.setMinimumSize(720, 480)
        self.resize(760, 520)

        self._build_ui()
        self.refresh_dependencies()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header
        title = QLabel("🛠️ System Dependencies & Tools")
        title.setObjectName("app-title")
        title.setFont(QFont("Montserrat", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        lbl_desc = QLabel(
            "YouTube Music Downloader relies on external command-line tools for audio transcoding, "
            "metadata tagging, and browser session authentication."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #B0B0B0;")
        layout.addWidget(lbl_desc)

        # Dependency Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Component", "Type", "Status", "Details"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Install Guide Card (shown if FFmpeg is missing)
        self.guide_card = QFrame()
        self.guide_card.setObjectName("card-frame")
        self.guide_card.setStyleSheet(
            "background-color: #2D1A1E; border: 1px solid #FF5252; border-radius: 8px; padding: 12px;"
        )
        guide_layout = QVBoxLayout(self.guide_card)
        guide_layout.setContentsMargins(8, 8, 8, 8)
        guide_layout.setSpacing(8)

        guide_title = QLabel("⚠️ Action Required: FFmpeg is missing")
        guide_title.setFont(QFont("Montserrat", 12, QFont.Weight.Bold))
        guide_title.setStyleSheet("color: #FF5252;")
        guide_layout.addWidget(guide_title)

        self.lbl_guide_text = QLabel()
        self.lbl_guide_text.setWordWrap(True)
        self.lbl_guide_text.setFont(QFont("JetBrains Mono", 10))
        self.lbl_guide_text.setStyleSheet(
            "background-color: #1A1214; color: #00E5FF; padding: 8px; border-radius: 4px;"
        )
        guide_layout.addWidget(self.lbl_guide_text)

        guide_btn_row = QHBoxLayout()
        btn_copy_cmd = QPushButton("📋 Copy Install Command")
        btn_copy_cmd.clicked.connect(self._copy_install_command)
        guide_btn_row.addWidget(btn_copy_cmd)
        guide_btn_row.addStretch()
        guide_layout.addLayout(guide_btn_row)

        layout.addWidget(self.guide_card)
        self.guide_card.setVisible(False)

        # Footer Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_refresh = QPushButton("🔄 Re-check")
        self.btn_refresh.clicked.connect(self.refresh_dependencies)
        btn_layout.addWidget(self.btn_refresh)

        btn_layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def refresh_dependencies(self):
        """Scan system dependencies and update table."""
        report = check_all_dependencies()
        self.table.setRowCount(len(report.items))

        ffmpeg_missing = False
        ffmpeg_guide = ""

        for row, item in enumerate(report.items):
            # 1. Component name
            item_name = QTableWidgetItem(item.name)
            item_name.setFont(QFont("Roboto", 10, QFont.Weight.Bold))
            self.table.setItem(row, 0, item_name)

            # 2. Type (Required / Optional)
            typ_text = "Required" if item.required else "Optional"
            item_type = QTableWidgetItem(typ_text)
            if item.required:
                item_type.setForeground(Qt.GlobalColor.red)
            else:
                item_type.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row, 1, item_type)

            # 3. Status
            if item.available:
                item_status = QTableWidgetItem("✓ Installed")
                item_status.setForeground(Qt.GlobalColor.green)
            else:
                if item.required:
                    item_status = QTableWidgetItem("✗ Missing")
                    item_status.setForeground(Qt.GlobalColor.red)
                    ffmpeg_missing = True
                    ffmpeg_guide = item.install_guide
                else:
                    item_status = QTableWidgetItem("! Not Found")
                    item_status.setForeground(Qt.GlobalColor.yellow)
            self.table.setItem(row, 2, item_status)

            # 4. Details (Version or Path)
            detail_str = item.version or item.path or item.description
            item_detail = QTableWidgetItem(detail_str)
            item_detail.setFont(QFont("JetBrains Mono", 9))
            self.table.setItem(row, 3, item_detail)

        if ffmpeg_missing:
            self.guide_card.setVisible(True)
            self.lbl_guide_text.setText(ffmpeg_guide or get_ffmpeg_install_guide())
        else:
            self.guide_card.setVisible(False)

    def _copy_install_command(self):
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self.lbl_guide_text.text().strip())
            QMessageBox.information(self, "Copied", "Installation command copied to clipboard!")
