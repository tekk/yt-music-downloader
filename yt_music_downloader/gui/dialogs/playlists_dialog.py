"""Modern modal dialog for exploring and selecting from user's YouTube Music playlists."""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...config import AppConfig
from ...downloader import UserPlaylistSummary, YTMusicDownloader


class FetchPlaylistsWorker(QThread):
    """Background worker fetching personal playlists."""

    success_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, downloader: YTMusicDownloader):
        super().__init__()
        self.downloader = downloader

    def run(self):
        try:
            playlists = self.downloader.fetch_user_playlists()
            self.success_signal.emit(playlists)
        except Exception as e:
            self.error_signal.emit(str(e))


class PlaylistsDialog(QDialog):
    """Modern modal dialog for searching and selecting user playlists."""

    def __init__(self, config: AppConfig, parent=None, auto_fetch: bool = True):
        super().__init__(parent)
        self.config = config
        self.downloader = YTMusicDownloader(config)
        self.setWindowTitle("My YouTube Music Playlists & Library")
        self.setMinimumSize(850, 560)

        self.worker: Optional[FetchPlaylistsWorker] = None
        self._all_playlists: List[UserPlaylistSummary] = []
        self._filtered_playlists: List[UserPlaylistSummary] = []
        self.selected_playlist: Optional[UserPlaylistSummary] = None

        self._build_ui()
        if auto_fetch:
            self.refresh_playlists()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header Title
        title = QLabel("📚 My YouTube Music Playlists")
        title.setObjectName("app-title")
        title.setFont(QFont("Montserrat", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Status / Feedback label
        self.lbl_status = QLabel("Fetching your playlists from YouTube Music...")
        self.lbl_status.setFont(QFont("Roboto", 12))
        self.lbl_status.setStyleSheet("color: #00E5FF; font-style: italic;")
        layout.addWidget(self.lbl_status)

        # Search Bar
        search_row = QHBoxLayout()
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("🔍 Search or filter playlists by name, channel, or ID...")
        self.input_search.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.input_search)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.refresh_playlists)
        search_row.addWidget(self.btn_refresh)
        layout.addLayout(search_row)

        # Playlists Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["#", "Title", "Tracks", "Channel / Uploader", "Playlist ID"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(3, 200)

        self.table.itemDoubleClicked.connect(self._on_double_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        # Bottom Buttons
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        self.btn_load = QPushButton("Load Playlist")
        self.btn_load.setObjectName("btn-download")
        self.btn_load.setEnabled(False)
        self.btn_load.clicked.connect(self._on_load_clicked)
        bottom_row.addWidget(self.btn_load)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_row.addWidget(self.btn_cancel)

        layout.addLayout(bottom_row)

    def refresh_playlists(self):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(1000)
        self.lbl_status.setText("Fetching your playlists from YouTube Music...")
        self.lbl_status.setStyleSheet("color: #00E5FF; font-style: italic;")
        self.btn_refresh.setEnabled(False)

        self.worker = FetchPlaylistsWorker(self.downloader)
        self.worker.success_signal.connect(self._on_playlists_loaded)
        self.worker.error_signal.connect(self._on_playlists_error)
        self.worker.start()

    def _on_playlists_loaded(self, playlists: List[UserPlaylistSummary]):
        self.btn_refresh.setEnabled(True)
        self._all_playlists = playlists
        self._apply_filter(self.input_search.text())
        if playlists:
            self.lbl_status.setText(f"✓ Found {len(playlists)} playlists in your library.")
            self.lbl_status.setStyleSheet("color: #00E676; font-weight: bold;")
        else:
            self.lbl_status.setText("No playlists found in your account.")
            self.lbl_status.setStyleSheet("color: #FFB300;")

    def _on_playlists_error(self, err_text: str):
        self.btn_refresh.setEnabled(True)
        if "401" in err_text or "Unauthorized" in err_text or "login" in err_text.lower():
            self.lbl_status.setText("Authentication expired. Please re-sync in Login / Cookies.")
            self.lbl_status.setStyleSheet("color: #FF5252; font-weight: bold;")
        else:
            self.lbl_status.setText(f"Error: {err_text}")
            self.lbl_status.setStyleSheet("color: #FF5252;")

    def _on_search_changed(self, text: str):
        self._apply_filter(text)

    def _apply_filter(self, query: str):
        q = query.strip().lower()
        if not q:
            self._filtered_playlists = list(self._all_playlists)
        else:
            self._filtered_playlists = [
                p for p in self._all_playlists
                if q in p.title.lower() or q in p.id.lower() or q in p.channel.lower()
            ]

        self.table.setRowCount(0)
        mono_font = QFont("JetBrains Mono", 11)
        body_font = QFont("Roboto", 12)

        for row_idx, p in enumerate(self._filtered_playlists):
            self.table.insertRow(row_idx)

            # 0: Index
            item_idx = QTableWidgetItem(f"{row_idx + 1:02d}")
            item_idx.setFont(mono_font)
            item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_idx.setForeground(QColor("#888888"))
            self.table.setItem(row_idx, 0, item_idx)

            # 1: Title
            item_title = QTableWidgetItem(p.title)
            item_title.setFont(body_font)
            item_title.setForeground(QColor("#FFFFFF"))
            self.table.setItem(row_idx, 1, item_title)

            # 2: Tracks
            tracks_text = f"{p.track_count}" if p.track_count is not None else "--"
            item_tracks = QTableWidgetItem(tracks_text)
            item_tracks.setFont(mono_font)
            item_tracks.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_tracks.setForeground(QColor("#00E5FF"))
            self.table.setItem(row_idx, 2, item_tracks)

            # 3: Channel
            item_channel = QTableWidgetItem(p.channel or "Unknown")
            item_channel.setFont(body_font)
            item_channel.setForeground(QColor("#B0B0B0"))
            self.table.setItem(row_idx, 3, item_channel)

            # 4: Playlist ID
            item_id = QTableWidgetItem(p.id)
            item_id.setFont(mono_font)
            item_id.setForeground(QColor("#777777"))
            self.table.setItem(row_idx, 4, item_id)

        self._on_selection_changed()

    def _on_selection_changed(self):
        selected_rows = self.table.selectedIndexes()
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self._filtered_playlists):
                self.selected_playlist = self._filtered_playlists[row]
                self.btn_load.setEnabled(True)
                return
        self.selected_playlist = None
        self.btn_load.setEnabled(False)

    def _on_double_clicked(self, item: QTableWidgetItem):
        row = item.row()
        if 0 <= row < len(self._filtered_playlists):
            self.selected_playlist = self._filtered_playlists[row]
            self.accept()

    def _on_load_clicked(self):
        if self.selected_playlist:
            self.accept()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(1000)
        super().closeEvent(event)

    def done(self, r):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(1000)
        super().done(r)
