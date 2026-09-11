"""Modern dark mode track table widget with status pills and responsive columns."""

from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from ...downloader import TrackInfo


class TrackTableWidget(QTableWidget):
    """Sleek dark mode table for displaying playlist tracks with status indicators."""

    COLUMNS = ["#", "Title", "Artist", "Duration", "Status"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)

        # Header sizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.setColumnWidth(2, 220)

        self._track_rows: Dict[int, int] = {}  # track.index -> row

    def clear_tracks(self) -> None:
        """Clear all rows and reset tracking indices."""
        self.setRowCount(0)
        self._track_rows.clear()

    def populate(self, tracks: List[TrackInfo]) -> None:
        """Clear and populate table with new tracks list."""
        self.clear_tracks()

        mono_font = QFont("JetBrains Mono", 11)
        body_font = QFont("Roboto", 12)

        for row_idx, track in enumerate(tracks):
            self.insertRow(row_idx)
            self._track_rows[track.index] = row_idx

            # 0: Index
            item_idx = QTableWidgetItem(f"{track.index:02d}")
            item_idx.setFont(mono_font)
            item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_idx.setForeground(QColor("#888888"))
            self.setItem(row_idx, 0, item_idx)

            # 1: Title
            item_title = QTableWidgetItem(track.title)
            item_title.setFont(body_font)
            item_title.setForeground(QColor("#FFFFFF"))
            self.setItem(row_idx, 1, item_title)

            # 2: Artist
            item_artist = QTableWidgetItem(track.artist)
            item_artist.setFont(body_font)
            item_artist.setForeground(QColor("#B0B0B0"))
            self.setItem(row_idx, 2, item_artist)

            # 3: Duration
            item_dur = QTableWidgetItem(track.duration_formatted)
            item_dur.setFont(mono_font)
            item_dur.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_dur.setForeground(QColor("#00E5FF"))
            self.setItem(row_idx, 3, item_dur)

            # 4: Status
            item_status = QTableWidgetItem(self._format_status_text(track))
            item_status.setFont(body_font)
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_status.setForeground(self._get_status_color(track.status))
            self.setItem(row_idx, 4, item_status)

    def update_track(self, track: TrackInfo) -> None:
        """Update live status and progress of a track."""
        row_idx = self._track_rows.get(track.index)
        if row_idx is None or row_idx >= self.rowCount():
            return

        item_status = self.item(row_idx, 4)
        if item_status:
            item_status.setText(self._format_status_text(track))
            item_status.setForeground(self._get_status_color(track.status))

    @staticmethod
    def _format_status_text(track: TrackInfo) -> str:
        if track.status == "Downloading" and track.percent > 0:
            return f"⬇ {track.percent:.0f}%"
        elif track.status == "Converting":
            return "🔄 Transcoding"
        elif track.status == "Done":
            return "✓ Done"
        elif track.status == "Error":
            return "✗ Error"
        elif track.status == "Skipped":
            return "↷ Skipped"
        return "⏳ Pending"

    @staticmethod
    def _get_status_color(status: str) -> QColor:
        if status == "Done":
            return QColor("#00E676")  # Green
        elif status == "Downloading":
            return QColor("#00E5FF")  # Cyan
        elif status == "Converting":
            return QColor("#FF9100")  # Amber
        elif status == "Error":
            return QColor("#FF5252")  # Red
        return QColor("#888888")       # Gray
