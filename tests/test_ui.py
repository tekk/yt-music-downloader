"""Asynchronous UI tests for YTMusicDownloaderApp using Textual test harness."""

import pytest
from textual.widgets import Button, Input, Label, ProgressBar, Select, TabbedContent

from yt_music_downloader.config import AppConfig
from yt_music_downloader.downloader import TrackInfo, UserPlaylistSummary
from yt_music_downloader.ui.app import YTMusicDownloaderApp
from yt_music_downloader.ui.screens.auth_modal import AuthModal
from yt_music_downloader.ui.screens.playlists_modal import PlaylistsModal
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

        # Verify tabs exist
        tabs = auth_screen.query_one("#auth-tabs", TabbedContent)
        assert tabs is not None

        # Verify buttons exist across tabs
        assert auth_screen.query_one("#btn-browser-login", Button) is not None
        assert auth_screen.query_one("#btn-sync-browser", Button) is not None
        assert auth_screen.query_one("#btn-load-file", Button) is not None
        assert auth_screen.query_one("#btn-clear-cookies", Button) is not None
        assert auth_screen.query_one("#btn-close", Button) is not None

        # Switch to Tab 2 (1-Click Sync)
        tabs.active = "tab-sync"
        await pilot.pause()
        select_browser = auth_screen.query_one("#select-browser", Select)
        assert select_browser.value == "chrome"

        # Switch to Tab 3 (Import File)
        tabs.active = "tab-import"
        await pilot.pause()
        # Test empty file load
        auth_screen.query_one("#btn-load-file", Button).press()
        await pilot.pause()
        feedback = auth_screen.query_one("#feedback-import", Label)
        assert "Please specify" in str(feedback.render())

        # Switch to Tab 4 (Cookie Status)
        tabs.active = "tab-info"
        await pilot.pause()
        info_status = auth_screen.query_one("#info-status", Label)
        assert info_status is not None

        # Close modal
        auth_screen.query_one("#btn-close", Button).press()
        await pilot.pause()


@pytest.mark.asyncio
async def test_escape_key_dismisses_settings_modal(tmp_path):
    cfg = AppConfig(download_dir=str(tmp_path), audio_format="mp3")
    app = YTMusicDownloaderApp(config=cfg)

    async with app.run_test() as pilot:
        settings_screen = SettingsModal(cfg)
        app.push_screen(settings_screen)
        await pilot.pause()
        assert len(app.screen_stack) == 2

        # Change format select to m4a (unsaved)
        format_select = settings_screen.query_one("#select-format", Select)
        format_select.value = "m4a"

        # Press escape - should dismiss without saving
        await pilot.press("escape")
        await pilot.pause()

        assert len(app.screen_stack) == 1
        assert cfg.audio_format == "mp3"


@pytest.mark.asyncio
async def test_escape_key_dismisses_auth_modal(tmp_path):
    cfg = AppConfig(cookies_path=str(tmp_path / "cookies.txt"))
    app = YTMusicDownloaderApp(config=cfg)

    async with app.run_test() as pilot:
        auth_screen = AuthModal(cfg)
        app.push_screen(auth_screen)
        await pilot.pause()
        assert len(app.screen_stack) == 2

        # Press escape - should dismiss
        await pilot.press("escape")
        await pilot.pause()

        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_escape_key_main_screen_actions(tmp_path):
    cfg = AppConfig(download_dir=str(tmp_path))
    app = YTMusicDownloaderApp(config=cfg)

    async with app.run_test() as pilot:
        # Focus the url input
        url_input = app.query_one("#url-input", Input)
        url_input.focus()
        await pilot.pause()
        assert app.focused == url_input

        # Press escape - should unfocus
        await pilot.press("escape")
        await pilot.pause()
        assert app.focused is None

        # Simulate downloading and test escape cancels download
        app._is_downloading = True
        assert not app.downloader._cancel_requested
        await pilot.press("escape")
        await pilot.pause()
        assert app.downloader._cancel_requested


@pytest.mark.asyncio
async def test_liked_songs_button_sets_url(tmp_path, monkeypatch):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsome_value\n")
    cfg = AppConfig(cookies_path=str(cookie_file), download_dir=str(tmp_path))
    app = YTMusicDownloaderApp(config=cfg)

    # Mock fetch_url_worker to prevent actual network calls during test
    monkeypatch.setattr(app, "fetch_url_worker", lambda url: None)

    async with app.run_test() as pilot:
        btn = app.query_one("#btn-liked-songs", Button)
        btn.press()
        await pilot.pause()

        url_input = app.query_one("#url-input", Input)
        assert url_input.value == "https://music.youtube.com/playlist?list=LM"


@pytest.mark.asyncio
async def test_playlists_modal_flow(tmp_path, monkeypatch):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsome_value\n")
    cfg = AppConfig(cookies_path=str(cookie_file), download_dir=str(tmp_path))
    app = YTMusicDownloaderApp(config=cfg)

    mock_playlists = [
        UserPlaylistSummary(id="LM", title="Liked Music", url="https://music.youtube.com/playlist?list=LM", track_count=100),
        UserPlaylistSummary(id="PL1", title="My DnB Mix", url="https://music.youtube.com/playlist?list=PL1", track_count=15),
    ]

    monkeypatch.setattr(app, "fetch_url_worker", lambda url: None)
    monkeypatch.setattr("yt_music_downloader.downloader.YTMusicDownloader.fetch_user_playlists", lambda self: mock_playlists)

    async with app.run_test() as pilot:
        # Press 'p' to open PlaylistsModal
        await pilot.press("p")
        await pilot.pause()

        assert len(app.screen_stack) == 2
        modal = app.screen_stack[-1]
        assert isinstance(modal, PlaylistsModal)

        # Wait for worker to populate
        await pilot.pause(0.1)

        # Filter for 'DnB'
        filter_input = modal.query_one("#playlists-filter-input", Input)
        filter_input.value = "DnB"
        await pilot.pause()

        assert len(modal._filtered_playlists) == 1
        assert modal._filtered_playlists[0].title == "My DnB Mix"

        # Select the playlist
        select_btn = modal.query_one("#btn-select-playlist", Button)
        select_btn.press()
        await pilot.pause()

        # Modal should be closed and URL input should be updated
        assert len(app.screen_stack) == 1
        url_input = app.query_one("#url-input", Input)
        assert url_input.value == "https://music.youtube.com/playlist?list=PL1"


@pytest.mark.asyncio
async def test_playlists_modal_escape_key(tmp_path, monkeypatch):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsome_value\n")
    cfg = AppConfig(cookies_path=str(cookie_file), download_dir=str(tmp_path))
    app = YTMusicDownloaderApp(config=cfg)

    monkeypatch.setattr("yt_music_downloader.downloader.YTMusicDownloader.fetch_user_playlists", lambda self: [])

    async with app.run_test() as pilot:
        modal = PlaylistsModal(cfg)
        app.push_screen(modal)
        await pilot.pause()
        assert len(app.screen_stack) == 2

        await pilot.press("escape")
        await pilot.pause()

        assert len(app.screen_stack) == 1


