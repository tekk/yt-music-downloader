"""Modern Settings modal dialog for PyQt6 desktop GUI."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ...config import AppConfig, get_default_music_dir


class SettingsDialog(QDialog):
    """Modal dialog for configuring application preferences."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Application Settings")
        self.setMinimumSize(640, 420)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("⚙ Application Settings")
        title.setObjectName("app-title")
        title.setFont(QFont("Montserrat", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # 1. Download Directory
        lbl_dir = QLabel("Default Download Directory:")
        lbl_dir.setObjectName("section-title")
        layout.addWidget(lbl_dir)

        dir_row = QHBoxLayout()
        self.input_dir = QLineEdit(self.config.download_dir)
        dir_row.addWidget(self.input_dir)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.btn_browse)

        self.btn_reset_dir = QPushButton("Reset")
        self.btn_reset_dir.clicked.connect(self._reset_dir)
        dir_row.addWidget(self.btn_reset_dir)
        layout.addLayout(dir_row)

        # 2. Audio Format & Quality Row
        format_row = QHBoxLayout()

        col_format = QVBoxLayout()
        lbl_format = QLabel("Default Audio Format:")
        lbl_format.setObjectName("section-title")
        col_format.addWidget(lbl_format)
        self.cb_format = QComboBox()
        self.cb_format.addItem("MP3 (Universal 320k)", "mp3")
        self.cb_format.addItem("M4A / AAC (Apple / Modern)", "m4a")
        self.cb_format.addItem("Original Best (No Transcoding)", "original")
        self.cb_format.addItem("FLAC (Lossless)", "flac")
        self.cb_format.addItem("OPUS (High Efficiency)", "opus")
        idx_fmt = self.cb_format.findData(self.config.audio_format)
        if idx_fmt >= 0:
            self.cb_format.setCurrentIndex(idx_fmt)
        self.cb_format.currentIndexChanged.connect(self._on_format_changed)
        col_format.addWidget(self.cb_format)
        format_row.addLayout(col_format)

        col_quality = QVBoxLayout()
        lbl_quality = QLabel("MP3 Bitrate Quality:")
        lbl_quality.setObjectName("section-title")
        col_quality.addWidget(lbl_quality)
        self.cb_quality = QComboBox()
        self.cb_quality.addItem("320 kbps (Highest CBR)", "320")
        self.cb_quality.addItem("256 kbps (High CBR)", "256")
        self.cb_quality.addItem("192 kbps (Standard CBR)", "192")
        self.cb_quality.addItem("VBR 0 (Best Variable)", "0")
        idx_q = self.cb_quality.findData(self.config.mp3_quality)
        if idx_q >= 0:
            self.cb_quality.setCurrentIndex(idx_q)
        col_quality.addWidget(self.cb_quality)
        format_row.addLayout(col_quality)

        layout.addLayout(format_row)

        # 3. Toggles
        lbl_opts = QLabel("Download Options:")
        lbl_opts.setObjectName("section-title")
        layout.addWidget(lbl_opts)

        self.chk_artwork = QCheckBox("Embed High-Resolution Album Artwork")
        self.chk_artwork.setChecked(self.config.embed_artwork)
        self.chk_artwork.setStyleSheet("font-size: 13px; font-weight: 500;")
        layout.addWidget(self.chk_artwork)

        self.chk_metadata = QCheckBox("Embed ID3 / Metadata Tags (Artist, Title, Year)")
        self.chk_metadata.setChecked(self.config.embed_metadata)
        self.chk_metadata.setStyleSheet("font-size: 13px; font-weight: 500;")
        layout.addWidget(self.chk_metadata)

        self.chk_playlist_folder = QCheckBox("Automatically Create Subfolder for Playlists")
        self.chk_playlist_folder.setChecked(self.config.auto_create_playlist_folder)
        self.chk_playlist_folder.setStyleSheet("font-size: 13px; font-weight: 500;")
        layout.addWidget(self.chk_playlist_folder)

        layout.addStretch()

        # 4. Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_save = QPushButton("Save & Apply")
        self.btn_save.setObjectName("btn-download")
        self.btn_save.clicked.connect(self._save_and_close)
        btn_row.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        layout.addLayout(btn_row)

        self._on_format_changed()

    def _browse_dir(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.input_dir.text())
        if chosen:
            self.input_dir.setText(chosen)

    def _reset_dir(self):
        self.input_dir.setText(str(get_default_music_dir()))

    def _on_format_changed(self):
        is_mp3 = self.cb_format.currentData() == "mp3"
        self.cb_quality.setEnabled(is_mp3)

    def _save_and_close(self):
        new_dir = self.input_dir.text().strip()
        if new_dir:
            self.config.download_dir = str(Path(new_dir).expanduser())
        self.config.audio_format = str(self.cb_format.currentData() or "mp3")
        self.config.mp3_quality = str(self.cb_quality.currentData() or "320")
        self.config.embed_artwork = self.chk_artwork.isChecked()
        self.config.embed_metadata = self.chk_metadata.isChecked()
        self.config.auto_create_playlist_folder = self.chk_playlist_folder.isChecked()
        self.config.save()
        self.accept()
