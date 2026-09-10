"""Interactive playlist tracks data table widget."""

from __future__ import annotations

from typing import Dict, List
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable

from ...downloader import TrackInfo


class TrackTable(Widget):
    """DataTable wrapper displaying playlist items and download progress."""

    DEFAULT_CSS = """
    TrackTable {
        height: 1fr;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._row_keys: Dict[int, str] = {}  # track_index -> row_key

    def compose(self) -> ComposeResult:
        table = DataTable(id="tracks-table", cursor_type="row", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("#", key="index")
        table.add_column("Title", key="title")
        table.add_column("Artist", key="artist")
        table.add_column("Duration", key="duration")
        table.add_column("Status", key="status")
        table.add_column("Progress", key="progress")

    def _render_status(self, status: str) -> Text:
        t = Text()
        if status == "Pending":
            t.append("⏳ Pending", style="dim")
        elif status == "Downloading":
            t.append("⬇ Downloading", style="bold cyan")
        elif status == "Converting":
            t.append("🔄 Transcoding", style="bold yellow")
        elif status == "Done":
            t.append("✓ Done", style="bold green")
        elif status == "Error":
            t.append("✗ Error", style="bold red")
        elif status == "Skipped":
            t.append("⏭ Skipped", style="dim yellow")
        else:
            t.append(status)
        return t

    def _render_progress(self, percent: float, status: str) -> Text:
        if status == "Done":
            return Text("100%", style="bold green")
        if status == "Pending":
            return Text("0%", style="dim")
        return Text(f"{percent:.0f}%", style="bold cyan")

    def populate(self, tracks: List[TrackInfo]) -> None:
        """Populate table with tracks list."""
        table = self.query_one(DataTable)
        table.clear()
        self._row_keys.clear()

        for track in tracks:
            status_text = self._render_status(track.status)
            progress_text = self._render_progress(track.percent, track.status)
            row_key = f"track-{track.index}"
            table.add_row(
                str(track.index),
                track.title,
                track.artist,
                track.duration_formatted,
                status_text,
                progress_text,
                key=row_key,
            )
            self._row_keys[track.index] = row_key

    def update_track(self, track: TrackInfo) -> None:
        """Update single row in the table."""
        table = self.query_one(DataTable)
        row_key = self._row_keys.get(track.index)
        if not row_key:
            return

        table.update_cell(row_key, "status", self._render_status(track.status))
        table.update_cell(row_key, "progress", self._render_progress(track.percent, track.status))

    def clear(self) -> None:
        """Clear all rows."""
        table = self.query_one(DataTable)
        table.clear()
        self._row_keys.clear()
