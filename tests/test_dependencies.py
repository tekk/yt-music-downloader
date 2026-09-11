"""Tests for system dependency detection and validation."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from yt_music_downloader.config import AppConfig
from yt_music_downloader.dependencies import (
    DependencyReport,
    DependencyStatus,
    check_all_dependencies,
    check_ffmpeg,
    check_ffprobe,
    get_ffmpeg_install_guide,
    get_os_info,
    print_dependency_report,
    verify_ffmpeg_requirement,
)
from yt_music_downloader.downloader import (
    DependencyError,
    PlaylistInfo,
    TrackInfo,
    YTMusicDownloader,
)


def test_check_ffmpeg_found():
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        with patch("yt_music_downloader.dependencies.get_binary_version", return_value="ffmpeg version 9.0"):
            status = check_ffmpeg()
            assert status.name == "FFmpeg"
            assert status.required is True
            assert status.available is True
            assert status.path == "/usr/bin/ffmpeg"
            assert status.version == "ffmpeg version 9.0"


def test_check_ffmpeg_missing():
    with patch("shutil.which", return_value=None):
        status = check_ffmpeg()
        assert status.name == "FFmpeg"
        assert status.required is True
        assert status.available is False
        assert status.path is None
        assert status.install_guide != ""


def test_check_ffprobe():
    with patch("shutil.which", return_value="/usr/bin/ffprobe"):
        with patch("yt_music_downloader.dependencies.get_binary_version", return_value="ffprobe version 9.0"):
            status = check_ffprobe()
            assert status.name == "FFprobe"
            assert status.required is False
            assert status.available is True


def test_get_ffmpeg_install_guide_os_variants():
    # macOS
    with patch("platform.system", return_value="Darwin"):
        guide = get_ffmpeg_install_guide()
        assert "brew install ffmpeg" in guide

    # Windows
    with patch("platform.system", return_value="Windows"):
        guide = get_ffmpeg_install_guide()
        assert "winget install Gyan.FFmpeg" in guide

    # Linux (Arch)
    with patch("platform.system", return_value="Linux"):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", unittest_mock_open("ID=arch\n")):
                guide = get_ffmpeg_install_guide()
                assert "pacman -S ffmpeg" in guide

    # Linux (Debian/Ubuntu)
    with patch("platform.system", return_value="Linux"):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", unittest_mock_open("ID=ubuntu\n")):
                guide = get_ffmpeg_install_guide()
                assert "apt update && sudo apt install ffmpeg" in guide


def unittest_mock_open(read_data=""):
    from unittest.mock import mock_open
    return mock_open(read_data=read_data)


def test_verify_ffmpeg_requirement_not_needed():
    cfg = AppConfig(
        audio_format="original",
        embed_artwork=False,
        embed_metadata=False,
    )
    with patch("shutil.which", return_value=None):
        ok, msg = verify_ffmpeg_requirement(cfg)
        assert ok is True
        assert msg == ""


def test_verify_ffmpeg_requirement_needed_and_missing():
    cfg = AppConfig(
        audio_format="mp3",
        embed_artwork=True,
    )
    with patch("shutil.which", return_value=None):
        ok, msg = verify_ffmpeg_requirement(cfg)
        assert ok is False
        assert "FFmpeg is required" in msg


def test_verify_ffmpeg_requirement_needed_and_available():
    cfg = AppConfig(
        audio_format="mp3",
        embed_artwork=True,
    )
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        ok, msg = verify_ffmpeg_requirement(cfg)
        assert ok is True
        assert msg == ""


def test_downloader_raises_dependency_error_when_ffmpeg_missing(tmp_path):
    cfg = AppConfig(
        download_dir=str(tmp_path),
        audio_format="mp3",
    )
    downloader = YTMusicDownloader(cfg)
    playlist = PlaylistInfo(
        title="Test",
        author="Tester",
        url="https://music.youtube.com/playlist?list=123",
        is_playlist=True,
        track_count=1,
        tracks=[TrackInfo(index=1, title="Track 1", artist="Artist 1", url="https://yt.com/1")],
    )

    with patch("shutil.which", return_value=None):
        logs = []
        with pytest.raises(DependencyError) as exc_info:
            downloader.download_playlist(
                playlist=playlist,
                on_track_update=lambda t: None,
                on_progress_update=lambda p: None,
                on_log=lambda m: logs.append(m),
            )
        assert "FFmpeg is required" in str(exc_info.value)
        assert any("Dependency Error" in log for log in logs)


def test_dependency_report_properties():
    report = DependencyReport(
        items=[
            DependencyStatus(name="Req1", required=True, available=True),
            DependencyStatus(name="Req2", required=True, available=False),
            DependencyStatus(name="Opt1", required=False, available=False),
        ]
    )
    assert report.all_required_met is False
    assert len(report.missing_required) == 1
    assert report.missing_required[0].name == "Req2"
    assert len(report.missing_optional) == 1
    assert report.missing_optional[0].name == "Opt1"


def test_print_dependency_report_output():
    report_ok = DependencyReport(
        items=[
            DependencyStatus(name="FFmpeg", required=True, available=True, path="/usr/bin/ffmpeg", version="v9"),
        ]
    )
    exit_code = print_dependency_report(report_ok)
    assert exit_code == 0

    report_missing = DependencyReport(
        items=[
            DependencyStatus(name="FFmpeg", required=True, available=False, install_guide="sudo apt install ffmpeg"),
        ]
    )
    exit_code_err = print_dependency_report(report_missing)
    assert exit_code_err == 1


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication([])
    return app


def test_gui_dependencies_dialog(qapp):
    from yt_music_downloader.gui.dialogs.dependencies_dialog import DependenciesDialog

    dlg = DependenciesDialog()
    assert dlg.table.rowCount() >= 2
    dlg.refresh_dependencies()
    assert dlg.windowTitle() == "System Dependencies & External Tools"

