"""CLI and integration tests for YT Music Downloader."""

import sys
from unittest.mock import MagicMock, patch
import pytest

from yt_music_downloader.cli import parse_args
from yt_music_downloader.config import AppConfig
from yt_music_downloader.downloader import (
    PlaylistInfo,
    TrackInfo,
    YTMusicDownloader,
)


def test_cli_parse_args():
    test_argv = [
        "yt-music-dl",
        "https://music.youtube.com/playlist?list=sample",
        "-f", "m4a",
        "-q", "256",
        "-o", "/tmp/music",
        "-t", "textual-light",
    ]
    with patch.object(sys, "argv", test_argv):
        args = parse_args()
        assert args.url == "https://music.youtube.com/playlist?list=sample"
        assert args.format == "m4a"
        assert args.quality == "256"
        assert args.output_dir == "/tmp/music"
        assert args.theme == "textual-light"


def test_downloader_mock_execution(tmp_path):
    cfg = AppConfig(
        download_dir=str(tmp_path),
        audio_format="mp3",
    )
    downloader = YTMusicDownloader(cfg)

    tracks = [
        TrackInfo(index=1, title="Test Track 1", artist="Artist 1", duration=120, url="https://yt.com/1"),
        TrackInfo(index=2, title="Test Track 2", artist="Artist 2", duration=180, url="https://yt.com/2"),
    ]
    playlist = PlaylistInfo(
        title="Test Playlist",
        author="Tester",
        url="https://yt.com/playlist",
        is_playlist=True,
        track_count=2,
        tracks=tracks,
    )

    track_updates = []
    progress_updates = []
    logs = []

    # Mock YoutubeDL instance
    with patch("yt_music_downloader.downloader.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance

        downloader.download_playlist(
            playlist=playlist,
            on_track_update=lambda t: track_updates.append((t.index, t.status)),
            on_progress_update=lambda p: progress_updates.append(p.overall_percent),
            on_log=lambda l: logs.append(l),
        )

        assert mock_instance.download.call_count == 2
        assert tracks[0].status == "Done"
        assert tracks[1].status == "Done"
        assert len(logs) > 0


def test_cli_parse_args_check_deps():
    with patch.object(sys, "argv", ["yt-music-dl", "--check-deps"]):
        args = parse_args()
        assert args.check_deps is True


def test_cli_main_check_deps_flow():
    from yt_music_downloader.cli import main
    with patch.object(sys, "argv", ["yt-music-dl", "--check-deps"]):
        with patch("yt_music_downloader.dependencies.print_dependency_report", return_value=0) as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            assert mock_print.call_count == 1


def test_cli_parse_args_gui_flag():
    with patch.object(sys, "argv", ["yt-music-dl", "--gui"]):
        args = parse_args()
        assert args.gui is True


def test_cli_parse_args_version():
    with patch.object(sys, "argv", ["yt-music-dl", "--version"]):
        with pytest.raises(SystemExit) as exc_info:
            parse_args()
        assert exc_info.value.code == 0


def test_cli_main_gui_launch():
    from yt_music_downloader.cli import main
    with patch.object(sys, "argv", ["yt-music-dl", "--gui"]):
        with patch("yt_music_downloader.gui.app.MainWindow") as mock_win_cls, \
             patch("PyQt6.QtWidgets.QApplication.exec", return_value=0):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            assert mock_win_cls.return_value.show.call_count == 1


def test_downloader_mock_execution_user_cancel(tmp_path):
    cfg = AppConfig(download_dir=str(tmp_path))
    downloader = YTMusicDownloader(cfg)

    tracks = [
        TrackInfo(index=1, title="Track 1", artist="Artist 1", duration=100, url="https://yt.com/1"),
        TrackInfo(index=2, title="Track 2", artist="Artist 2", duration=100, url="https://yt.com/2"),
    ]
    playlist = PlaylistInfo(title="Cancel List", author="Tester", url="https://yt.com/pl", is_playlist=True, track_count=2, tracks=tracks)

    track_updates = []
    logs = []

    def cancel_after_first_track(t):
        track_updates.append(t.status)
        if t.status == "Downloading" and t.index == 1:
            # Trigger cancellation during first track download
            downloader.cancel()

    with patch("yt_music_downloader.downloader.yt_dlp.YoutubeDL") as mock_ydl_cls:
        downloader.download_playlist(
            playlist=playlist,
            on_track_update=cancel_after_first_track,
            on_progress_update=lambda p: None,
            on_log=lambda l: logs.append(l),
        )
        # Track 1 was downloaded, then cancel halted the loop before track 2
        assert mock_ydl_cls.return_value.__enter__.return_value.download.call_count == 1
        assert tracks[0].status == "Done"
        assert tracks[1].status == "Skipped"


def test_downloader_mock_execution_error_handling(tmp_path):
    cfg = AppConfig(download_dir=str(tmp_path))
    downloader = YTMusicDownloader(cfg)

    tracks = [
        TrackInfo(index=1, title="Failing Track", artist="Artist 1", duration=100, url="https://yt.com/fail"),
    ]
    playlist = PlaylistInfo(title="Fail List", author="Tester", url="https://yt.com/pl", is_playlist=False, track_count=1, tracks=tracks)

    with patch("yt_music_downloader.downloader.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()
        mock_instance.download.side_effect = RuntimeError("Extraction failed")
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance

        downloader.download_playlist(
            playlist=playlist,
            on_track_update=lambda t: None,
            on_progress_update=lambda p: None,
            on_log=lambda l: None,
        )

        assert tracks[0].status == "Error"
        assert "Extraction failed" in tracks[0].error_message


def test_downloader_progress_and_postprocessor_hooks(tmp_path):
    cfg = AppConfig(download_dir=str(tmp_path), audio_format="mp3")
    downloader = YTMusicDownloader(cfg)

    tracks = [
        TrackInfo(index=1, title="Progress Track", artist="Artist 1", duration=200, url="https://yt.com/prog"),
    ]
    playlist = PlaylistInfo(title="Progress List", author="Tester", url="https://yt.com/pl", is_playlist=False, track_count=1, tracks=tracks)

    progress_events = []
    log_events = []

    with patch("yt_music_downloader.downloader.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()

        def fake_download(urls):
            # Capture the opts passed to _build_ydl_opts
            call_opts = mock_ydl_cls.call_args[0][0]
            progress_hook = call_opts["progress_hooks"][0]
            pp_hook = call_opts["postprocessor_hooks"][0]

            # Simulate progress update
            progress_hook({
                "status": "downloading",
                "downloaded_bytes": 1000,
                "total_bytes": 2000,
                "speed": 500,
                "eta": 2,
            })

            # Simulate postprocessor hooks
            pp_hook({"status": "started", "postprocessor": "FFmpegExtractAudio"})
            pp_hook({"status": "started", "postprocessor": "EmbedThumbnail"})
            pp_hook({"status": "started", "postprocessor": "FFmpegMetadata"})
            pp_hook({"status": "started", "postprocessor": "OtherPP"})

        mock_instance.download.side_effect = fake_download
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance

        downloader.download_playlist(
            playlist=playlist,
            on_track_update=lambda t: None,
            on_progress_update=lambda p: progress_events.append(p),
            on_log=lambda l: log_events.append(l),
        )

        assert len(progress_events) >= 5
        assert progress_events[0].track_percent == 50.0
        assert any("Re-encoding" in l for l in log_events)
        assert any("cover art" in l for l in log_events)
        assert any("metadata tags" in l for l in log_events)


