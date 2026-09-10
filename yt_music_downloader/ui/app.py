"""Main Textual Application for YouTube Music Downloader."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    TabbedContent,
    TabPane,
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
from .screens.auth_modal import AuthModal
from .screens.playlists_modal import PlaylistsModal
from .screens.settings_modal import SettingsModal
from .widgets.progress_panel import ProgressPanel
from .widgets.track_table import TrackTable


class YTMusicDownloaderApp(App):
    """Modern cross-platform TUI for downloading YouTube Music with highest quality."""

    TITLE = "YouTube Music Downloader"
    SUB_TITLE = "Highest Audio Quality • Re-encode MP3/M4A • Browser Cookie Grabber"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("t", "toggle_theme", "Toggle Dark/Light", priority=True),
        Binding("f2", "toggle_theme", "Toggle Dark/Light", show=False),
        Binding("l", "open_auth", "Login / Cookies", priority=True),
        Binding("p", "open_playlists", "My Playlists", priority=True),
        Binding("s", "open_settings", "Settings", priority=True),
        Binding("d", "start_download", "Download", priority=True),
        Binding("c", "cancel_download", "Cancel", priority=True),
        Binding("i", "inspect_url", "Inspect URL", priority=True),
        Binding("escape", "handle_escape", "Cancel / Back", show=False),
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self, config: Optional[AppConfig] = None, initial_url: Optional[str] = None):
        super().__init__()
        self.config = config or AppConfig.load()
        self.initial_url = initial_url or ""
        self.downloader = YTMusicDownloader(self.config)
        self.current_playlist: Optional[PlaylistInfo] = None
        self._is_downloading = False

    def on_mount(self) -> None:
        """Apply theme and initial state on startup."""
        self.theme = self.config.theme or "textual-dark"
        self.update_auth_indicator()
        if self.initial_url:
            input_widget = self.query_one("#url-input", Input)
            input_widget.value = self.initial_url
            self.action_inspect_url()

    def compose(self) -> ComposeResult:
        # Header bar with Auth and Theme indicators
        with Horizontal(id="header-container"):
            yield Label("🎵 YouTube Music Downloader", id="app-title")
            yield Button("🔓 Login", id="auth-badge", classes="auth-guest")
            yield Button("🌓 Theme", id="btn-header-theme", variant="default")

        # URL Input and Options Panel
        with Vertical(id="input-panel"):
            with Horizontal(id="input-row"):
                yield Input(
                    placeholder="Enter YouTube Music URL (Playlist, Album, or Song)...",
                    id="url-input",
                )
                yield Button("🔍 Inspect", id="inspect-btn", variant="primary")
                yield Button("♥ Liked Songs", id="btn-liked-songs", variant="default")
                yield Button("📚 My Playlists", id="btn-my-playlists", variant="default")

            with Horizontal(id="options-row"):
                with Horizontal(classes="option-item"):
                    yield Label("Format:", classes="option-label")
                    formats = [
                        ("MP3 (320 kbps High Quality)", "mp3"),
                        ("M4A / AAC (256 kbps)", "m4a"),
                        ("Original Best (Opus/M4A)", "original"),
                        ("FLAC (Lossless)", "flac"),
                        ("OPUS (High Efficiency)", "opus"),
                    ]
                    yield Select(formats, value=self.config.audio_format, id="format-select")

                with Horizontal(classes="option-item"):
                    yield Label("Quality:", classes="option-label")
                    qualities = [
                        ("320 kbps", "320"),
                        ("256 kbps", "256"),
                        ("192 kbps", "192"),
                        ("VBR 0", "0"),
                    ]
                    yield Select(qualities, value=self.config.mp3_quality, id="quality-select")

        # Content Area with Tracklist and Log Tabs
        with TabbedContent(id="content-tabs"):
            with TabPane("🎶 Tracks & Queue", id="tab-tracks"):
                yield TrackTable(id="tracks-widget")

            with TabPane("📋 Activity Log", id="tab-log"):
                yield RichLog(id="log-view", highlight=True, markup=True)

        # Dual Progress Indicator
        yield ProgressPanel(id="progress-panel")

        # Action Buttons Bar
        with Horizontal(id="actions-bar"):
            yield Button("⬇ Download All", id="download-btn", classes="action-btn")
            yield Button("🛑 Cancel", id="cancel-btn", classes="action-btn", disabled=True)
            yield Button("🔐 Login / Cookies", id="login-btn", classes="action-btn")
            yield Button("⚙ Settings", id="settings-btn", classes="action-btn")
            yield Button("🌓 Theme", id="theme-btn", classes="action-btn")

        yield Footer()

    def update_auth_indicator(self) -> None:
        """Update top-right auth pill button based on cookies status."""
        status = check_cookie_file(self.config.cookies_path)
        badge = self.query_one("#auth-badge", Button)
        if status.is_authenticated:
            badge.label = f"🔒 Logged In ({status.count})"
            badge.classes = "auth-logged-in"
        elif status.exists:
            badge.label = f"⚠ Cookies ({status.count})"
            badge.classes = "auth-guest"
        else:
            badge.label = "🔓 Login"
            badge.classes = "auth-guest"

    def log_message(self, message: str) -> None:
        """Write to activity log."""
        try:
            log_view = self.query_one("#log-view", RichLog)
            log_view.write(message)
        except Exception:
            pass

    # Button handlers
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "inspect-btn":
            self.action_inspect_url()
        elif btn_id == "btn-liked-songs":
            self.action_load_liked_songs()
        elif btn_id == "btn-my-playlists":
            self.action_open_playlists()
        elif btn_id == "download-btn":
            self.action_start_download()
        elif btn_id == "cancel-btn":
            self.action_cancel_download()
        elif btn_id in ("login-btn", "auth-badge"):
            self.action_open_auth()
        elif btn_id == "settings-btn":
            self.action_open_settings()
        elif btn_id in ("theme-btn", "btn-header-theme"):
            self.action_toggle_theme()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url-input":
            self.action_inspect_url()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "format-select":
            self.config.audio_format = str(event.value or "mp3")
            quality_select = self.query_one("#quality-select", Select)
            quality_select.disabled = self.config.audio_format != "mp3"
            self.config.save()
        elif event.select.id == "quality-select":
            self.config.mp3_quality = str(event.value or "320")
            self.config.save()

    # Actions
    def action_toggle_theme(self) -> None:
        """Toggle between Dark and Light mode."""
        if self.theme in ("textual-dark", "nord", "dracula", "solarized-dark", "tokyo-night", "gruvbox"):
            new_theme = "textual-light"
        else:
            new_theme = "textual-dark"
        self.theme = new_theme
        self.config.theme = new_theme
        self.config.save()
        self.log_message(f"Theme switched to [bold]{new_theme}[/bold]")

    def action_load_liked_songs(self) -> None:
        """Load user's Liked Music (LM) playlist."""
        if not self.config.has_cookies():
            self.log_message("[yellow]Notice: You must log in via 'Login / Cookies' to access your personal Liked Songs.[/yellow]")
            self.action_open_auth()
            return

        self.log_message("[bold cyan]Loading Liked Songs from YouTube Music...[/bold cyan]")
        url_input = self.query_one("#url-input", Input)
        url_input.value = "https://music.youtube.com/playlist?list=LM"
        self.action_inspect_url()

    def action_open_playlists(self) -> None:
        """Open modal to browse and select user's personal playlists."""
        if not self.config.has_cookies():
            self.log_message("[yellow]Notice: You must log in via 'Login / Cookies' to access your personal playlists.[/yellow]")
            self.action_open_auth()
            return

        def handle_playlist_selected(selected: Optional[UserPlaylistSummary]):
            if selected:
                self.log_message(f"[bold cyan]Selected playlist:[/bold cyan] {selected.title}")
                url_input = self.query_one("#url-input", Input)
                url_input.value = selected.url
                self.action_inspect_url()

        self.push_screen(PlaylistsModal(self.config), handle_playlist_selected)

    def action_open_auth(self) -> None:
        """Open Authentication and Cookie Grabber modal."""
        def handle_auth_result(result: Optional[AppConfig]):
            if result:
                self.config = result
                self.downloader.config = result
            self.update_auth_indicator()

        self.push_screen(AuthModal(self.config), handle_auth_result)

    def action_open_settings(self) -> None:
        """Open Settings modal."""
        def handle_settings_result(result: Optional[AppConfig]):
            if result:
                self.config = result
                self.downloader.config = result
                self.theme = result.theme
                self.query_one("#format-select", Select).value = result.audio_format
                self.query_one("#quality-select", Select).value = result.mp3_quality

        self.push_screen(SettingsModal(self.config), handle_settings_result)

    def action_inspect_url(self) -> None:
        """Fetch tracklist metadata in background thread."""
        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            self.log_message("[red]Please enter a YouTube Music URL.[/red]")
            return

        self.fetch_url_worker(url)

    @work(thread=True)
    def fetch_url_worker(self, url: str) -> None:
        """Inspect and parse URL metadata without blocking UI."""
        self.call_from_thread(self.log_message, f"Fetching playlist info for [cyan]{url}[/cyan]...")
        self.call_from_thread(self.query_one("#inspect-btn", Button).set_class, True, "-loading")

        try:
            playlist_info = self.downloader.fetch_info(url)
            self.current_playlist = playlist_info

            def update_ui():
                self.query_one("#inspect-btn", Button).set_class(False, "-loading")
                table = self.query_one("#tracks-widget", TrackTable)
                table.populate(playlist_info.tracks)
                self.log_message(
                    f"[bold green]✓ Loaded:[/bold green] [bold]{playlist_info.title}[/bold] by {playlist_info.author} ({playlist_info.track_count} tracks)"
                )
                panel = self.query_one("#progress-panel", ProgressPanel)
                panel.reset()
                panel.update_overall(0, playlist_info.track_count, 0.0)
                panel.set_status(f"Ready to download {playlist_info.track_count} tracks")

            self.call_from_thread(update_ui)

        except Exception as e:
            def report_error():
                self.query_one("#inspect-btn", Button).set_class(False, "-loading")
                self.log_message(f"[bold red]Failed to fetch URL:[/bold red] {e}")

            self.call_from_thread(report_error)

    def action_start_download(self) -> None:
        """Start downloading current playlist in background thread."""
        if not self.current_playlist or not self.current_playlist.tracks:
            # If no playlist loaded yet, try inspecting the URL first
            url = self.query_one("#url-input", Input).value.strip()
            if url:
                self.action_inspect_url()
            else:
                self.log_message("[red]Please enter a URL and inspect tracks before downloading.[/red]")
            return

        if self._is_downloading:
            return

        self._is_downloading = True
        self.query_one("#download-btn", Button).disabled = True
        self.query_one("#cancel-btn", Button).disabled = False

        self.download_worker(self.current_playlist)

    def action_cancel_download(self) -> None:
        """Cancel the active download."""
        if self._is_downloading:
            self.log_message("[yellow]Cancelling download...[/yellow]")
            self.downloader.cancel()
            panel = self.query_one("#progress-panel", ProgressPanel)
            panel.set_status("Cancelling...")

    def action_handle_escape(self) -> None:
        """Handle Esc keypress: dismiss modal, cancel download, or clear focus."""
        if len(self.screen_stack) > 1:
            try:
                self.pop_screen()
            except Exception:
                pass
        elif self._is_downloading:
            self.action_cancel_download()
        elif self.focused:
            self.set_focus(None)

    @work(thread=True)
    def download_worker(self, playlist: PlaylistInfo) -> None:
        """Execute downloads in background thread."""
        self.call_from_thread(
            self.log_message,
            f"[bold cyan]Starting download of '{playlist.title}' ({playlist.track_count} tracks)[/bold cyan]",
        )

        def on_track_update(track: TrackInfo):
            def ui():
                self.query_one("#tracks-widget", TrackTable).update_track(track)
            self.call_from_thread(ui)

        def on_progress_update(p: DownloadProgressUpdate):
            def ui():
                panel = self.query_one("#progress-panel", ProgressPanel)
                panel.update_track(
                    percent=p.track_percent,
                    downloaded=p.downloaded_bytes,
                    total=p.total_bytes,
                    speed=p.speed,
                    eta=p.eta,
                    status_text=f"[{p.track_index}/{p.total_tracks}] {p.track_artist} - {p.track_title}: {p.status_text}",
                )
                panel.update_overall(
                    completed=p.overall_completed,
                    total=p.total_tracks,
                    percent=p.overall_percent,
                )
            self.call_from_thread(ui)

        def on_log(msg: str):
            self.call_from_thread(self.log_message, msg)

        try:
            self.downloader.download_playlist(
                playlist=playlist,
                on_track_update=on_track_update,
                on_progress_update=on_progress_update,
                on_log=on_log,
            )
        except Exception as e:
            self.call_from_thread(self.log_message, f"[bold red]Download error:[/bold red] {e}")
        finally:
            def finish_ui():
                self._is_downloading = False
                self.query_one("#download-btn", Button).disabled = False
                self.query_one("#cancel-btn", Button).disabled = True
                panel = self.query_one("#progress-panel", ProgressPanel)
                panel.set_status("Download finished")

            self.call_from_thread(finish_ui)
