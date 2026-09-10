"""Modal dialog for browsing and selecting playlists from user's YouTube Music library."""

from __future__ import annotations

from typing import List, Optional

from rich.markup import escape
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label

from ...config import AppConfig
from ...downloader import UserPlaylistSummary, YTMusicDownloader


class PlaylistsModal(ModalScreen[Optional[UserPlaylistSummary]]):
    """Modal dialog for selecting from user's library playlists."""

    BINDINGS = [
        Binding("escape", "cancel_modal", "Close", priority=True),
    ]

    DEFAULT_CSS = """
    PlaylistsModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #playlists-dialog {
        width: 88;
        height: 85%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    .modal-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        border-bottom: solid $surface-lighten-1;
        padding-bottom: 1;
    }
    #playlists-status {
        height: 1;
        margin-bottom: 1;
        color: $accent;
        text-style: italic;
    }
    #playlists-filter-row {
        height: 3;
        margin-bottom: 1;
        layout: horizontal;
    }
    #playlists-filter-input {
        width: 1fr;
    }
    #playlists-table {
        height: 1fr;
        border: round $surface-lighten-2;
        margin-bottom: 1;
    }
    .modal-buttons {
        height: 3;
        layout: horizontal;
        align: right middle;
    }
    .modal-buttons Button {
        min-width: 16;
        margin-left: 1;
    }
    """

    def __init__(self, config: AppConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.downloader = YTMusicDownloader(config)
        self._all_playlists: List[UserPlaylistSummary] = []
        self._filtered_playlists: List[UserPlaylistSummary] = []
        self._selected_playlist: Optional[UserPlaylistSummary] = None

    def action_cancel_modal(self) -> None:
        """Close modal without selection on Esc."""
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        with Vertical(id="playlists-dialog"):
            yield Label("📚 My YouTube Music Playlists", id="modal-title", classes="modal-title")
            yield Label("Fetching your playlists from YouTube Music...", id="playlists-status")

            with Horizontal(id="playlists-filter-row"):
                yield Input(placeholder="🔍 Search or filter playlists by name...", id="playlists-filter-input")

            yield DataTable(id="playlists-table", cursor_type="row")

            with Horizontal(classes="modal-buttons"):
                yield Button("Load Playlist", id="btn-select-playlist", variant="primary", disabled=True)
                yield Button("Refresh", id="btn-refresh-playlists", variant="default")
                yield Button("Cancel", id="btn-close-playlists", variant="default")

    def on_mount(self) -> None:
        table = self.query_one("#playlists-table", DataTable)
        table.add_columns("#", "Title", "Tracks", "Channel / Uploader", "Playlist ID")
        self.fetch_playlists_worker()

    @work(thread=True)
    def fetch_playlists_worker(self) -> None:
        """Fetch playlists in background thread."""
        try:
            playlists = self.downloader.fetch_user_playlists()

            def update_ui():
                self._all_playlists = playlists
                self._apply_filter("")
                status_lbl = self.query_one("#playlists-status", Label)
                if playlists:
                    status_lbl.update(Text.from_markup(f"[green]Found {len(playlists)} playlists in your library.[/green]"))
                else:
                    status_lbl.update(Text.from_markup("[yellow]No playlists found in your account.[/yellow]"))

            self.app.call_from_thread(update_ui)
        except Exception as e:
            def report_err():
                status_lbl = self.query_one("#playlists-status", Label)
                err_text = str(e)
                if "401" in err_text or "Unauthorized" in err_text or "does not exist" in err_text:
                    status_lbl.update(
                        Text.from_markup(
                            "[bold red]Session cookies expired or unauthorized.[/bold red] Please re-sync in [bold]Login / Cookies[/bold]."
                        )
                    )
                else:
                    status_lbl.update(Text.from_markup(f"[bold red]Error fetching playlists:[/bold red] {escape(err_text)}"))

            self.app.call_from_thread(report_err)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "playlists-filter-input":
            self._apply_filter(event.value)

    def _apply_filter(self, query: str) -> None:
        query_norm = query.strip().lower()
        if not query_norm:
            self._filtered_playlists = list(self._all_playlists)
        else:
            self._filtered_playlists = [
                p for p in self._all_playlists
                if query_norm in p.title.lower() or query_norm in p.id.lower() or query_norm in p.channel.lower()
            ]

        table = self.query_one("#playlists-table", DataTable)
        table.clear()
        for idx, p in enumerate(self._filtered_playlists, start=1):
            tracks_str = str(p.track_count) if p.track_count is not None else "--"
            table.add_row(
                str(idx),
                p.title,
                tracks_str,
                p.channel or "Unknown",
                p.id,
                key=p.id,
            )

        btn = self.query_one("#btn-select-playlist", Button)
        btn.disabled = len(self._filtered_playlists) == 0

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = str(event.row_key.value)
        selected = next((p for p in self._filtered_playlists if p.id == row_key), None)
        if selected:
            self.dismiss(selected)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key:
            row_key = str(event.row_key.value)
            self._selected_playlist = next((p for p in self._filtered_playlists if p.id == row_key), None)
            btn = self.query_one("#btn-select-playlist", Button)
            btn.disabled = self._selected_playlist is None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-select-playlist":
            if self._selected_playlist:
                self.dismiss(self._selected_playlist)
            elif self._filtered_playlists:
                self.dismiss(self._filtered_playlists[0])
        elif btn_id == "btn-refresh-playlists":
            status_lbl = self.query_one("#playlists-status", Label)
            status_lbl.update(Text.from_markup("[cyan]Refreshing playlists...[/cyan]"))
            self.fetch_playlists_worker()
        elif btn_id == "btn-close-playlists":
            self.dismiss(None)
