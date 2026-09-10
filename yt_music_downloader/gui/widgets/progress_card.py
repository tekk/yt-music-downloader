"""Modern dual progress card widget for track and overall playlist indicators."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


def _format_bytes(b: int) -> str:
    """Format bytes to human readable KB/MB/GB string."""
    if not b or b <= 0:
        return "0 MB"
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} TB"


def _format_speed(bps: float) -> str:
    if not bps or bps <= 0:
        return "-- MB/s"
    return f"{bps / (1024 * 1024):.1f} MB/s"


def _format_eta(seconds: int) -> str:
    if not seconds or seconds <= 0:
        return "--:--"
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


class ProgressCardWidget(QFrame):
    """Sleek dark card displaying real-time dual progress bars, speed, and status ticker."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card-frame")

        mono_font = QFont("JetBrains Mono", 11)
        header_font = QFont("Montserrat", 11, QFont.Weight.Bold)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 1. Status Ticker Row
        self.lbl_status = QLabel("Ready to download")
        self.lbl_status.setFont(QFont("Roboto", 12))
        self.lbl_status.setStyleSheet("color: #00E5FF; font-weight: 500;")
        layout.addWidget(self.lbl_status)

        # 2. Track Progress Row
        track_row = QHBoxLayout()
        lbl_track_title = QLabel("CURRENT TRACK")
        lbl_track_title.setFont(header_font)
        lbl_track_title.setStyleSheet("color: #888888; font-size: 10px; letter-spacing: 1px;")
        track_row.addWidget(lbl_track_title)
        track_row.addStretch()

        self.lbl_stats = QLabel("0 MB / 0 MB • -- MB/s • ETA: --:--")
        self.lbl_stats.setFont(mono_font)
        self.lbl_stats.setStyleSheet("color: #CCCCCC;")
        track_row.addWidget(self.lbl_stats)
        layout.addLayout(track_row)

        self.track_bar = QProgressBar()
        self.track_bar.setRange(0, 100)
        self.track_bar.setValue(0)
        self.track_bar.setTextVisible(True)
        self.track_bar.setFormat("%p%")
        layout.addWidget(self.track_bar)

        # 3. Overall Playlist Progress Row
        overall_row = QHBoxLayout()
        lbl_overall_title = QLabel("OVERALL PLAYLIST")
        lbl_overall_title.setFont(header_font)
        lbl_overall_title.setStyleSheet("color: #888888; font-size: 10px; letter-spacing: 1px;")
        overall_row.addWidget(lbl_overall_title)
        overall_row.addStretch()

        self.lbl_overall_stats = QLabel("0 / 0 tracks (0%)")
        self.lbl_overall_stats.setFont(mono_font)
        self.lbl_overall_stats.setStyleSheet("color: #00E5FF;")
        overall_row.addWidget(self.lbl_overall_stats)
        layout.addLayout(overall_row)

        self.overall_bar = QProgressBar()
        self.overall_bar.setObjectName("overall-bar")
        self.overall_bar.setRange(0, 100)
        self.overall_bar.setValue(0)
        self.overall_bar.setTextVisible(True)
        self.overall_bar.setFormat("%p%")
        layout.addWidget(self.overall_bar)

    def update_track(
        self,
        percent: float,
        downloaded: int = 0,
        total: int = 0,
        speed: float = 0.0,
        eta: int = 0,
        status_text: str = "",
    ) -> None:
        """Update single track progress indicators."""
        self.track_bar.setValue(int(min(max(percent, 0.0), 100.0)))
        stat_str = f"{_format_bytes(downloaded)} / {_format_bytes(total)} • {_format_speed(speed)} • ETA: {_format_eta(eta)}"
        self.lbl_stats.setText(stat_str)
        if status_text:
            self.lbl_status.setText(status_text)

    def update_overall(self, completed: int, total: int, percent: float) -> None:
        """Update overall playlist progress bar and counter."""
        self.overall_bar.setValue(int(min(max(percent, 0.0), 100.0)))
        self.lbl_overall_stats.setText(f"{completed} / {total} tracks ({percent:.0f}%)")

    def set_status(self, text: str) -> None:
        """Update live status ticker banner."""
        self.lbl_status.setText(text)

    def reset(self) -> None:
        """Reset progress bars to zero."""
        self.track_bar.setValue(0)
        self.overall_bar.setValue(0)
        self.lbl_stats.setText("0 MB / 0 MB • -- MB/s • ETA: --:--")
        self.lbl_overall_stats.setText("0 / 0 tracks (0%)")
        self.lbl_status.setText("Ready to download")
