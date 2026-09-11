"""Automated tests for Desktop PyQt6 GUI components in offscreen mode."""

import os
import pytest

# Ensure Qt runs headlessly in offscreen mode during tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from yt_music_downloader.config import AppConfig
from yt_music_downloader.downloader import PlaylistInfo, TrackInfo, UserPlaylistSummary
from yt_music_downloader.gui.app import MainWindow
from yt_music_downloader.gui.dialogs.auth_dialog import AuthDialog
from yt_music_downloader.gui.dialogs.playlists_dialog import PlaylistsDialog
from yt_music_downloader.gui.dialogs.settings_dialog import SettingsDialog
from yt_music_downloader.gui.styles import DARK_THEME_QSS, load_application_fonts
from yt_music_downloader.gui.widgets.progress_card import ProgressCardWidget
from yt_music_downloader.gui.widgets.track_table import TrackTableWidget


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    load_application_fonts()
    app.setStyleSheet(DARK_THEME_QSS)
    return app


def test_custom_fonts_registered(qapp):
    """Verify Montserrat, Roboto, and JetBrains Mono fonts are loaded."""
    families = load_application_fonts()
    assert families["title"] == "Montserrat"
    assert families["body"] == "Roboto"
    assert families["mono"] == "JetBrains Mono"


def test_main_window_mount_and_widgets(qapp, tmp_path):
    """Test MainWindow initialization, layout, and child widgets."""
    cfg = AppConfig(download_dir=str(tmp_path), audio_format="mp3")
    win = MainWindow(config=cfg)

    assert win.input_url is not None
    assert win.btn_inspect is not None
    assert win.btn_liked is not None
    assert win.btn_playlists is not None
    assert win.cb_format is not None
    assert win.cb_quality is not None
    assert win.track_table is not None
    assert win.progress_card is not None
    assert win.btn_download is not None
    assert win.btn_cancel is not None
    win.close()


def test_liked_songs_action(qapp, tmp_path, monkeypatch):
    """Test clicking Liked Songs button populates LM playlist URL."""
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsome_value\n")
    cfg = AppConfig(cookies_path=str(cookie_file), download_dir=str(tmp_path))
    win = MainWindow(config=cfg)

    monkeypatch.setattr(win, "inspect_url", lambda: None)
    win.load_liked_songs()

    assert win.input_url.text() == "https://music.youtube.com/playlist?list=LM"
    win.close()


def test_track_table_widget(qapp):
    """Test TrackTableWidget populating and updating rows."""
    table = TrackTableWidget()
    tracks = [
        TrackInfo(index=1, title="Song 1", artist="Artist 1", duration=180),
        TrackInfo(index=2, title="Song 2", artist="Artist 2", duration=240),
    ]
    table.populate(tracks)
    assert table.rowCount() == 2
    assert table.item(0, 1).text() == "Song 1"
    assert table.item(1, 2).text() == "Artist 2"

    tracks[0].status = "Downloading"
    tracks[0].percent = 50.0
    table.update_track(tracks[0])
    assert "50%" in table.item(0, 4).text()

    tracks[0].status = "Done"
    table.update_track(tracks[0])
    assert "Done" in table.item(0, 4).text()


def test_progress_card_widget(qapp):
    """Test ProgressCardWidget updating track and overall stats."""
    card = ProgressCardWidget()
    card.update_track(percent=75.0, downloaded=1500000, total=2000000, speed=500000, eta=1)
    assert card.track_bar.value() == 75
    assert "ETA: 00:01" in card.lbl_stats.text()

    card.update_overall(completed=3, total=10, percent=30.0)
    assert card.overall_bar.value() == 30
    assert "3 / 10 tracks" in card.lbl_overall_stats.text()

    card.reset()
    assert card.track_bar.value() == 0
    assert card.overall_bar.value() == 0


def test_settings_dialog_save(qapp, tmp_path):
    """Test SettingsDialog updates and saves configuration."""
    cfg = AppConfig(download_dir=str(tmp_path), audio_format="mp3", mp3_quality="320")
    dialog = SettingsDialog(cfg)

    # Change format to m4a
    idx = dialog.cb_format.findData("m4a")
    dialog.cb_format.setCurrentIndex(idx)
    dialog._save_and_close()

    assert cfg.audio_format == "m4a"


def test_playlists_dialog_filter(qapp, tmp_path, monkeypatch):
    """Test PlaylistsDialog filtering and selection."""
    cfg = AppConfig(download_dir=str(tmp_path))
    dialog = PlaylistsDialog(cfg, auto_fetch=False)

    mock_playlists = [
        UserPlaylistSummary(id="LM", title="Liked Music", url="https://music.youtube.com/playlist?list=LM", track_count=50),
        UserPlaylistSummary(id="PL_EDM", title="EDM Party", url="https://music.youtube.com/playlist?list=PL_EDM", track_count=20),
        UserPlaylistSummary(id="PL_ROCK", title="Rock Classics", url="https://music.youtube.com/playlist?list=PL_ROCK", track_count=35),
    ]

    dialog._on_playlists_loaded(mock_playlists)
    assert dialog.table.rowCount() == 3

    # Filter for 'Party'
    dialog.input_search.setText("Party")
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 1).text() == "EDM Party"

    # Select the item
    dialog.table.selectRow(0)
    assert dialog.selected_playlist is not None
    assert dialog.selected_playlist.id == "PL_EDM"
    dialog.close()


def test_auth_dialog_rendering(qapp, tmp_path):
    """Test AuthDialog initializes tabs and status properly."""
    cfg = AppConfig(download_dir=str(tmp_path), cookies_path=str(tmp_path / "nonexistent.txt"))
    dialog = AuthDialog(cfg)
    assert dialog.tabs.count() == 4
    assert "Not Authenticated" in dialog.lbl_status_summary.text()
    dialog.close()


def test_main_window_shortcuts(qapp, tmp_path):
    """Test registered keyboard shortcuts on MainWindow."""
    cfg = AppConfig(download_dir=str(tmp_path))
    win = MainWindow(config=cfg)

    shortcuts = [a.shortcut().toString() for a in win.actions() if not a.shortcut().isEmpty()]
    assert "Ctrl+D" in shortcuts
    assert "Ctrl+L" in shortcuts
    assert "Ctrl+P" in shortcuts
    assert "Ctrl+," in shortcuts
    assert "Ctrl+Q" in shortcuts
    assert "Esc" in shortcuts

    # Test escape handling
    win._is_downloading = False
    win._handle_escape()  # should not crash

    win.close()


def test_main_window_dependencies_button_and_banner(qapp, tmp_path):
    """Test MainWindow dependencies button and missing banner visibility."""
    from unittest.mock import patch
    cfg = AppConfig(download_dir=str(tmp_path))

    # 1. When ffmpeg is available
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        win = MainWindow(config=cfg)
        assert hasattr(win, "btn_deps")
        assert win.banner_ffmpeg.isHidden() is True
        win.close()

    # 2. When ffmpeg is missing
    with patch("shutil.which", return_value=None):
        win_missing = MainWindow(config=cfg)
        assert win_missing.banner_ffmpeg.isHidden() is False
        win_missing.close()


def test_progress_card_widget_reset(qapp):
    card = ProgressCardWidget()
    card.update_track(percent=50.0, downloaded=1000, total=2000, speed=500, eta=2)
    card.update_overall(completed=1, total=2, percent=50.0)
    assert card.track_bar.value() == 50

    card.reset()
    assert card.track_bar.value() == 0
    assert card.overall_bar.value() == 0
    assert "Ready" in card.lbl_status.text()


def test_track_table_widget_clear(qapp):
    table = TrackTableWidget()
    tracks = [
        TrackInfo(index=1, title="Song 1", artist="Artist 1", duration=180),
    ]
    table.populate(tracks)
    assert table.rowCount() == 1

    table.clear_tracks()
    assert table.rowCount() == 0


def test_main_window_log_and_ui_states(qapp, tmp_path):
    cfg = AppConfig(download_dir=str(tmp_path))
    win = MainWindow(config=cfg)

    # Test log appending
    win.log_message("Test log entry")
    assert "Test log entry" in win.log_console.toPlainText()

    # Test inspect success UI updates
    info = PlaylistInfo(
        title="My Playlist",
        author="Artist",
        url="https://music.youtube.com/playlist?list=123",
        is_playlist=True,
        track_count=1,
        tracks=[TrackInfo(index=1, title="Song 1", artist="Artist 1", duration=100)],
    )
    win._on_inspect_success(info)
    assert win.current_playlist == info
    assert win.track_table.rowCount() == 1
    assert "Loaded 'My Playlist'" in win.progress_card.lbl_status.text()

    # Test inspect error UI updates
    win._on_inspect_error("Failed to connect")
    assert "Failed to connect" in win.progress_card.lbl_status.text()

    win.close()


def test_app_icon_loading(qapp):
    """Verify get_app_icon loads a valid, non-null QIcon and icon path exists."""
    from yt_music_downloader.gui.styles import get_app_icon, get_app_icon_path

    icon_path = get_app_icon_path()
    assert icon_path.exists()

    icon = get_app_icon()
    assert not icon.isNull()
    sizes = icon.availableSizes()
    assert len(sizes) > 0


def test_main_window_window_icon(qapp, tmp_path):
    """Verify MainWindow has a valid window icon set upon initialization."""
    cfg = AppConfig(download_dir=str(tmp_path))
    win = MainWindow(config=cfg)
    assert not win.windowIcon().isNull()
    win.close()


