"""Main PyQt6 Desktop GUI Application for YouTube Music Downloader."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..browser_auth import check_cookie_file
from ..config import AppConfig
from ..downloader import (
    DownloadProgressUpdate,
    PlaylistInfo,
    TrackInfo,
    UserPlaylistSummary,
    YTMusicDownloader,
)
from .dialogs.auth_dialog import AuthDialog
from .dialogs.playlists_dialog import PlaylistsDialog
from .dialogs.settings_dialog import SettingsDialog
from .styles import DARK_THEME_QSS, load_application_fonts
from .widgets.progress_card import ProgressCardWidget
from .widgets.track_table import TrackTableWidget


class InspectWorker(QThread):
    """Background worker inspecting URL metadata."""

    success_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, downloader: YTMusicDownloader, url: str):
        super().__init__()
        self.downloader = downloader
        self.url = url

    def run(self):
        try:
            info = self.downloader.fetch_info(self.url)
            self.success_signal.emit(info)
        except Exception as e:
            self.error_signal.emit(str(e))


class DownloadWorker(QThread):
    """Background worker downloading playlist tracks."""

    track_update_signal = pyqtSignal(object)
    progress_update_signal = pyqtSignal(object)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, downloader: YTMusicDownloader, playlist: PlaylistInfo):
        super().__init__()
        self.downloader = downloader
        self.playlist = playlist

    def run(self):
        try:
            self.downloader.download_playlist(
                playlist=self.playlist,
                on_track_update=lambda t: self.track_update_signal.emit(t),
                on_progress_update=lambda p: self.progress_update_signal.emit(p),
                on_log=lambda m: self.log_signal.emit(m),
            )
            self.finished_signal.emit(True, "Download completed successfully!")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class MainWindow(QMainWindow):
    """Modern Desktop GUI MainWindow for YouTube Music Downloader."""

    def __init__(self, config: Optional[AppConfig] = None, initial_url: str = ""):
        super().__init__()
        self.config = config or AppConfig.load()
        self.downloader = YTMusicDownloader(self.config)
        self.current_playlist: Optional[PlaylistInfo] = None
        self.inspect_worker: Optional[InspectWorker] = None
        self.download_worker: Optional[DownloadWorker] = None
        self._is_downloading = False

        self.setWindowTitle("YouTube Music Downloader")
        self.setMinimumSize(1000, 720)
        self.resize(1120, 780)

        self._build_ui()
        self._setup_shortcuts()
        self.update_auth_badge()

        if initial_url:
            self.input_url.setText(initial_url)
            self.inspect_url()

    def _build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(12)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        lbl_app = QLabel("🎵 YouTube Music Downloader")
        lbl_app.setObjectName("app-title")
        lbl_app.setFont(QFont("Montserrat", 18, QFont.Weight.Bold))
        header_layout.addWidget(lbl_app)
        header_layout.addStretch()

        self.btn_auth = QPushButton("🔓 Login")
        self.btn_auth.setObjectName("auth-badge")
        self.btn_auth.clicked.connect(self.open_auth_dialog)
        header_layout.addWidget(self.btn_auth)

        self.btn_settings = QPushButton("⚙ Settings")
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        header_layout.addWidget(self.btn_settings)

        main_layout.addLayout(header_layout)

        # 2. Input Card (URL, Inspect, Liked Songs, My Playlists)
        input_card = QFrame()
        input_card.setObjectName("card-frame")
        card_layout = QVBoxLayout(input_card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("Enter YouTube Music URL (Playlist, Album, Song, or Artist)...")
        self.input_url.returnPressed.connect(self.inspect_url)
        url_row.addWidget(self.input_url)

        self.btn_inspect = QPushButton("🔍 Inspect")
        self.btn_inspect.setObjectName("btn-inspect")
        self.btn_inspect.clicked.connect(self.inspect_url)
        url_row.addWidget(self.btn_inspect)

        self.btn_liked = QPushButton("♥ Liked Songs")
        self.btn_liked.setObjectName("btn-liked-songs")
        self.btn_liked.clicked.connect(self.load_liked_songs)
        url_row.addWidget(self.btn_liked)

        self.btn_playlists = QPushButton("📚 My Playlists")
        self.btn_playlists.setObjectName("btn-my-playlists")
        self.btn_playlists.clicked.connect(self.open_playlists_dialog)
        url_row.addWidget(self.btn_playlists)

        card_layout.addLayout(url_row)

        # Options Row
        opts_row = QHBoxLayout()
        opts_row.setSpacing(12)

        lbl_fmt = QLabel("Format:")
        lbl_fmt.setStyleSheet("font-weight: bold; color: #B0B0B0;")
        opts_row.addWidget(lbl_fmt)

        self.cb_format = QComboBox()
        self.cb_format.addItem("MP3 (Universal 320k)", "mp3")
        self.cb_format.addItem("M4A / AAC (Apple 256k)", "m4a")
        self.cb_format.addItem("Original Best (No Re-encoding)", "original")
        self.cb_format.addItem("FLAC (Lossless)", "flac")
        self.cb_format.addItem("OPUS (High Efficiency)", "opus")
        idx_f = self.cb_format.findData(self.config.audio_format)
        if idx_f >= 0:
            self.cb_format.setCurrentIndex(idx_f)
        self.cb_format.currentIndexChanged.connect(self._on_format_changed)
        opts_row.addWidget(self.cb_format)

        lbl_q = QLabel("Quality:")
        lbl_q.setStyleSheet("font-weight: bold; color: #B0B0B0;")
        opts_row.addWidget(lbl_q)

        self.cb_quality = QComboBox()
        self.cb_quality.addItem("320 kbps (Highest CBR)", "320")
        self.cb_quality.addItem("256 kbps (High CBR)", "256")
        self.cb_quality.addItem("192 kbps (Standard CBR)", "192")
        self.cb_quality.addItem("VBR 0 (Best Variable)", "0")
        idx_q = self.cb_quality.findData(self.config.mp3_quality)
        if idx_q >= 0:
            self.cb_quality.setCurrentIndex(idx_q)
        self.cb_quality.currentIndexChanged.connect(self._on_quality_changed)
        opts_row.addWidget(self.cb_quality)

        self.btn_browse_dir = QPushButton("📁 " + Path(self.config.download_dir).name)
        self.btn_browse_dir.setToolTip(f"Download Directory: {self.config.download_dir}")
        self.btn_browse_dir.clicked.connect(self._choose_download_dir)
        opts_row.addWidget(self.btn_browse_dir)

        opts_row.addStretch()

        self.btn_download = QPushButton("⬇ Start Download")
        self.btn_download.setObjectName("btn-download")
        self.btn_download.clicked.connect(self.start_download)
        opts_row.addWidget(self.btn_download)

        self.btn_cancel = QPushButton("⏹ Cancel")
        self.btn_cancel.setObjectName("btn-cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_download)
        opts_row.addWidget(self.btn_cancel)

        card_layout.addLayout(opts_row)
        main_layout.addWidget(input_card)

        # 3. Center Tabs (Track List and Log)
        self.tabs = QTabWidget()

        self.track_table = TrackTableWidget()
        self.tabs.addTab(self.track_table, "📋 Track List")

        self.log_console = QPlainTextEdit()
        self.log_console.setObjectName("log-console")
        self.log_console.setReadOnly(True)
        self.tabs.addTab(self.log_console, "📜 Activity & Process Log")

        main_layout.addWidget(self.tabs, stretch=1)

        # 4. Bottom Progress Card
        self.progress_card = ProgressCardWidget()
        main_layout.addWidget(self.progress_card)

        self._on_format_changed()

    def _setup_shortcuts(self):
        # Ctrl+D: Download
        act_dl = QAction(self)
        act_dl.setShortcut(QKeySequence("Ctrl+D"))
        act_dl.triggered.connect(self.start_download)
        self.addAction(act_dl)

        # Ctrl+L: Liked Songs
        act_liked = QAction(self)
        act_liked.setShortcut(QKeySequence("Ctrl+L"))
        act_liked.triggered.connect(self.load_liked_songs)
        self.addAction(act_liked)

        # Ctrl+P: My Playlists
        act_pl = QAction(self)
        act_pl.setShortcut(QKeySequence("Ctrl+P"))
        act_pl.triggered.connect(self.open_playlists_dialog)
        self.addAction(act_pl)

        # Esc: Cancel active download
        act_esc = QAction(self)
        act_esc.setShortcut(QKeySequence("Escape"))
        act_esc.triggered.connect(self._handle_escape)
        self.addAction(act_esc)

    def _handle_escape(self):
        if self._is_downloading:
            self.cancel_download()

    def update_auth_badge(self):
        status = check_cookie_file(self.config.cookies_path)
        if status.is_authenticated:
            self.btn_auth.setText(f"🔒 Logged In ({status.count})")
            self.btn_auth.setProperty("authenticated", "true")
        elif status.exists:
            self.btn_auth.setText(f"⚠ Cookies ({status.count})")
            self.btn_auth.setProperty("authenticated", "false")
        else:
            self.btn_auth.setText("🔓 Login")
            self.btn_auth.setProperty("authenticated", "false")
        self.btn_auth.style().unpolish(self.btn_auth)
        self.btn_auth.style().polish(self.btn_auth)

    def log_message(self, message: str):
        self.log_console.appendPlainText(message)

    # Actions
    def inspect_url(self):
        url = self.input_url.text().strip()
        if not url:
            self.log_message("Please enter a YouTube Music URL.")
            return

        self.btn_inspect.setEnabled(False)
        self.btn_inspect.setText("Fetching...")
        self.progress_card.set_status(f"Inspecting URL: {url}")
        self.log_message(f"Fetching playlist info for {url}...")

        self.inspect_worker = InspectWorker(self.downloader, url)
        self.inspect_worker.success_signal.connect(self._on_inspect_success)
        self.inspect_worker.error_signal.connect(self._on_inspect_error)
        self.inspect_worker.start()

    def _on_inspect_success(self, info: PlaylistInfo):
        self.btn_inspect.setEnabled(True)
        self.btn_inspect.setText("🔍 Inspect")
        self.current_playlist = info
        self.track_table.populate(info.tracks)
        self.tabs.setCurrentIndex(0)  # Switch to track list

        msg = f"✓ Loaded '{info.title}' ({info.track_count} tracks)"
        self.progress_card.set_status(msg)
        self.log_message(f"Successfully loaded '{info.title}' ({info.track_count} tracks by {info.author})")

    def _on_inspect_error(self, err: str):
        self.btn_inspect.setEnabled(True)
        self.btn_inspect.setText("🔍 Inspect")
        self.progress_card.set_status(f"Inspection error: {err}")
        self.log_message(f"Failed to fetch URL: {err}")

    def load_liked_songs(self):
        """1-click load user's Liked Music (LM) playlist."""
        if not self.config.has_cookies():
            QMessageBox.information(
                self,
                "Authentication Required",
                "You need to log in to YouTube Music to load your Liked Songs.\n"
                "Please click 'Login' in the upper right corner.",
            )
            self.open_auth_dialog()
            return

        self.input_url.setText("https://music.youtube.com/playlist?list=LM")
        self.inspect_url()

    def open_playlists_dialog(self):
        """Open user playlists library modal."""
        if not self.config.has_cookies():
            QMessageBox.information(
                self,
                "Authentication Required",
                "You need to log in to YouTube Music to access your personal playlists.\n"
                "Please click 'Login' in the upper right corner.",
            )
            self.open_auth_dialog()
            return

        dialog = PlaylistsDialog(self.config, self)
        if dialog.exec() == PlaylistsDialog.DialogCode.Accepted and dialog.selected_playlist:
            p = dialog.selected_playlist
            self.log_message(f"Selected library playlist: '{p.title}'")
            self.input_url.setText(p.url)
            self.inspect_url()

    def open_auth_dialog(self):
        dialog = AuthDialog(self.config, self)
        dialog.exec()
        self.update_auth_badge()
        self.downloader.config = self.config

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self.downloader.config = self.config
            idx_f = self.cb_format.findData(self.config.audio_format)
            if idx_f >= 0:
                self.cb_format.setCurrentIndex(idx_f)
            idx_q = self.cb_quality.findData(self.config.mp3_quality)
            if idx_q >= 0:
                self.cb_quality.setCurrentIndex(idx_q)
            self.btn_browse_dir.setText("📁 " + Path(self.config.download_dir).name)
            self.btn_browse_dir.setToolTip(f"Download Directory: {self.config.download_dir}")

    def start_download(self):
        if not self.current_playlist or not self.current_playlist.tracks:
            url = self.input_url.text().strip()
            if url:
                self.inspect_url()
            else:
                QMessageBox.warning(self, "No URL", "Please enter a URL and inspect tracks before downloading.")
            return

        if self._is_downloading:
            return

        self._is_downloading = True
        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_card.reset()

        self.log_message(f"Starting download of '{self.current_playlist.title}' ({self.current_playlist.track_count} tracks)...")

        self.download_worker = DownloadWorker(self.downloader, self.current_playlist)
        self.download_worker.track_update_signal.connect(self.track_table.update_track)
        self.download_worker.progress_update_signal.connect(self._on_download_progress)
        self.download_worker.log_signal.connect(self.log_message)
        self.download_worker.finished_signal.connect(self._on_download_finished)
        self.download_worker.start()

    def cancel_download(self):
        if self._is_downloading:
            self.log_message("Cancelling download...")
            self.downloader.cancel()
            self.progress_card.set_status("Cancelling download...")

    def _on_download_progress(self, p: DownloadProgressUpdate):
        self.progress_card.update_track(
            percent=p.track_percent,
            downloaded=p.downloaded_bytes,
            total=p.total_bytes,
            speed=p.speed,
            eta=p.eta,
            status_text=f"[{p.track_index}/{p.total_tracks}] {p.track_artist} - {p.track_title}: {p.status_text}",
        )
        self.progress_card.update_overall(
            completed=p.overall_completed,
            total=p.total_tracks,
            percent=p.overall_percent,
        )

    def _on_download_finished(self, success: bool, message: str):
        self._is_downloading = False
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_card.set_status(message)
        self.log_message(f"Download process ended: {message}")

    def _on_format_changed(self):
        fmt = self.cb_format.currentData()
        self.config.audio_format = str(fmt or "mp3")
        self.cb_quality.setEnabled(self.config.audio_format == "mp3")
        self.config.save()

    def _on_quality_changed(self):
        q = self.cb_quality.currentData()
        self.config.mp3_quality = str(q or "320")
        self.config.save()

    def _choose_download_dir(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.config.download_dir)
        if chosen:
            self.config.download_dir = chosen
            self.config.save()
            self.btn_browse_dir.setText("📁 " + Path(chosen).name)
            self.btn_browse_dir.setToolTip(f"Download Directory: {chosen}")

    def closeEvent(self, event):
        if self.inspect_worker and self.inspect_worker.isRunning():
            self.inspect_worker.quit()
            self.inspect_worker.wait(1000)
        if self.download_worker and self.download_worker.isRunning():
            self.downloader.cancel()
            self.download_worker.quit()
            self.download_worker.wait(1000)
        super().closeEvent(event)


def main():
    """Launch the Desktop GUI Application."""
    # High-DPI scaling configuration
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Music Downloader")
    app.setOrganizationName("Tekk")

    # Load custom fonts: Montserrat, Roboto, JetBrains Mono
    load_application_fonts()

    # Apply modern dark QSS stylesheet
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
