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
