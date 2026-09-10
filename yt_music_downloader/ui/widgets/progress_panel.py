"""Comprehensive dual progress indicator widget for YouTube Music Downloader."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label, ProgressBar


def format_bytes(b: int | float) -> str:
    """Format bytes into human-readable string."""
    if not b or b <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} TB"


def format_time(seconds: int | float) -> str:
    """Format seconds into MM:SS."""
    if not seconds or seconds < 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


class ProgressPanel(Widget):
    """Widget containing current track and overall playlist progress bars."""

    DEFAULT_CSS = """
    ProgressPanel {
        height: auto;
        padding: 1;
        background: $surface;
        border: solid $primary;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="progress-inner"):
            # Current Track Progress
            with Horizontal(classes="progress-row"):
                yield Label("Current Track:", classes="progress-label")
                yield Label("0.0% • 0 B / 0 B", id="current-stat", classes="progress-stat")

            with Horizontal():
                yield ProgressBar(id="current-progress-bar", total=100, show_eta=False)

            # Overall Playlist Progress
            with Horizontal(classes="progress-row"):
                yield Label("Overall:", classes="progress-label")
                yield Label("0 / 0 tracks (0%)", id="overall-stat", classes="progress-stat")

            with Horizontal():
                yield ProgressBar(id="overall-progress-bar", total=100, show_eta=False)

            # Status ticker
            yield Label("Status: Ready", id="status-ticker")

    def update_track(
        self,
        percent: float,
        downloaded: int,
        total: int,
        speed: float,
        eta: int,
        status_text: str = "",
    ) -> None:
        """Update single track progress."""
        bar = self.query_one("#current-progress-bar", ProgressBar)
        bar.progress = min(100.0, max(0.0, percent))

        stat_label = self.query_one("#current-stat", Label)
        dl_str = format_bytes(downloaded)
        tot_str = format_bytes(total) if total > 0 else "--"
        speed_str = f"{format_bytes(speed)}/s" if speed > 0 else "--"
        eta_str = f"ETA {format_time(eta)}" if eta > 0 else ""

        stat_parts = [f"{percent:.1f}%", f"{dl_str} / {tot_str}"]
        if speed_str != "--":
            stat_parts.append(speed_str)
        if eta_str:
            stat_parts.append(eta_str)

        stat_label.update(" • ".join(stat_parts))

        if status_text:
            self.set_status(status_text)

    def update_overall(self, completed: int, total: int, percent: float) -> None:
        """Update overall playlist progress."""
        bar = self.query_one("#overall-progress-bar", ProgressBar)
        bar.progress = min(100.0, max(0.0, percent))

        stat_label = self.query_one("#overall-stat", Label)
        stat_label.update(f"{completed} / {total} tracks ({percent:.1f}%)")

    def set_status(self, text: str) -> None:
        """Set the status ticker text."""
        ticker = self.query_one("#status-ticker", Label)
        ticker.update(f"Status: {text}")

    def reset(self) -> None:
        """Reset progress bars to zero."""
        self.query_one("#current-progress-bar", ProgressBar).progress = 0
        self.query_one("#overall-progress-bar", ProgressBar).progress = 0
        self.query_one("#current-stat", Label).update("0.0% • 0 B / 0 B")
        self.query_one("#overall-stat", Label).update("0 / 0 tracks (0%)")
        self.set_status("Ready")
