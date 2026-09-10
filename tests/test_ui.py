"""Asynchronous UI tests for YTMusicDownloaderApp using Textual test harness."""

import pytest
from textual.widgets import Button, Input, ProgressBar, Select

from yt_music_downloader.config import AppConfig
from yt_music_downloader.downloader import TrackInfo
from yt_music_downloader.ui.app import YTMusicDownloaderApp
from yt_music_downloader.ui.screens.auth_modal import AuthModal
from yt_music_downloader.ui.screens.settings_modal import SettingsModal
from yt_music_downloader.ui.widgets.progress_panel import ProgressPanel
from yt_music_downloader.ui.widgets.track_table import TrackTable


@pytest.mark.asyncio
async def test_app_mount_and_widgets(tmp_path):
    cfg = AppConfig(
        download_dir=str(tmp_path),
        cookies_path=str(tmp_path / "cookies.txt"),
        theme="textual-dark",
    )
    app = YTMusicDownloaderApp(config=cfg)

    async with app.run_test() as pilot:
        # Check core widgets exist
        assert app.query_one("#url-input", Input) is not None
        assert app.query_one("#inspect-btn", Button) is not None
        assert app.query_one("#download-btn", Button) is not None
        assert app.query_one("#progress-panel", ProgressPanel) is not None
        assert app.query_one("#tracks-widget", TrackTable) is not None

        # Check initial theme
        assert app.theme == "textual-dark"

        # Test toggle theme
        app.action_toggle_theme()
        assert app.theme == "textual-light"
        app.action_toggle_theme()
        assert app.theme == "textual-dark"


@pytest.mark.asyncio
async def test_progress_panel_and_track_table(tmp_path):
    cfg = AppConfig(download_dir=str(tmp_path))
    app = YTMusicDownloaderApp(config=cfg)

    async with app.run_test() as pilot:
        panel = app.query_one("#progress-panel", ProgressPanel)
        panel.update_track(
            percent=50.0,
            downloaded=5000000,
            total=10000000,
            speed=2500000,
            eta=2,
            status_text="Downloading...",
        )
        cur_bar = panel.query_one("#current-progress-bar", ProgressBar)
        assert cur_bar.progress == 50.0

        panel.update_overall(completed=5, total=10, percent=50.0)
        overall_bar = panel.query_one("#overall-progress-bar", ProgressBar)
        assert overall_bar.progress == 50.0

        table_widget = app.query_one("#tracks-widget", TrackTable)
        tracks = [
            TrackInfo(index=1, title="Song A", artist="Artist A", duration=180),
            TrackInfo(index=2, title="Song B", artist="Artist B", duration=240),
        ]
        table_widget.populate(tracks)

        # Update track 1 status
        tracks[0].status = "Done"
        tracks[0].percent = 100.0
        table_widget.update_track(tracks[0])


@pytest.mark.asyncio
async def test_settings_modal_flow(tmp_path):
    cfg = AppConfig(download_dir=str(tmp_path), audio_format="mp3")
    app = YTMusicDownloaderApp(config=cfg)

    async with app.run_test() as pilot:
        settings_screen = SettingsModal(cfg)
        app.push_screen(settings_screen)
        await pilot.pause()

        # Change format select to m4a
        format_select = settings_screen.query_one("#select-format", Select)
        format_select.value = "m4a"

        # Press save
        save_btn = settings_screen.query_one("#btn-save", Button)
        save_btn.press()
        await pilot.pause()

        assert cfg.audio_format == "m4a"


@pytest.mark.asyncio
async def test_auth_modal_flow(tmp_path):
    cfg = AppConfig(cookies_path=str(tmp_path / "cookies.txt"))
    app = YTMusicDownloaderApp(config=cfg)

    async with app.run_test() as pilot:
        auth_screen = AuthModal(cfg)
        app.push_screen(auth_screen)
        await pilot.pause()

        # Verify buttons exist
        assert auth_screen.query_one("#btn-browser-login", Button) is not None
        assert auth_screen.query_one("#btn-sync-browser", Button) is not None
        assert auth_screen.query_one("#btn-close", Button) is not None

        # Close modal
        auth_screen.query_one("#btn-close", Button).press()
        await pilot.pause()
