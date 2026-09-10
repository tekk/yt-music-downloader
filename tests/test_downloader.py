"""Unit tests for downloader engine and formatting."""

import pytest
from yt_music_downloader.config import AppConfig
from yt_music_downloader.downloader import (
    PlaylistInfo,
    TrackInfo,
    YTMusicDownloader,
)


def test_track_info_duration_format():
    t1 = TrackInfo(index=1, title="Song 1", artist="Artist 1", duration=45)
    assert t1.duration_formatted == "00:45"

    t2 = TrackInfo(index=2, title="Song 2", artist="Artist 2", duration=215)
    assert t2.duration_formatted == "03:35"

    t3 = TrackInfo(index=3, title="Long Song", artist="Artist 3", duration=3665)
    assert t3.duration_formatted == "1:01:05"

    t4 = TrackInfo(index=4, title="Unknown Duration", artist="Artist 4", duration=0)
    assert t4.duration_formatted == "--:--"


def test_downloader_build_ydl_opts_mp3():
    cfg = AppConfig(
        audio_format="mp3",
        mp3_quality="320",
        embed_artwork=True,
        embed_metadata=True,
    )
    downloader = YTMusicDownloader(cfg)
    opts = downloader._build_ydl_opts("out.mp3", lambda d: None, lambda d: None)

    assert opts["format"] == "bestaudio/best"
    assert opts["writethumbnail"] is True

    pp_keys = [p["key"] for p in opts["postprocessors"]]
    assert "FFmpegExtractAudio" in pp_keys
    assert "FFmpegMetadata" in pp_keys
    assert "EmbedThumbnail" in pp_keys

    extract_pp = next(p for p in opts["postprocessors"] if p["key"] == "FFmpegExtractAudio")
    assert extract_pp["preferredcodec"] == "mp3"
    assert extract_pp["preferredquality"] == "320"


def test_downloader_build_ydl_opts_original():
    cfg = AppConfig(
        audio_format="original",
        embed_artwork=False,
        embed_metadata=False,
    )
    downloader = YTMusicDownloader(cfg)
    opts = downloader._build_ydl_opts("out.opus", lambda d: None, lambda d: None)

    assert opts["format"] == "bestaudio/best"
    assert opts.get("writethumbnail") is False
    # No FFmpegExtractAudio when format is 'original'
    assert "postprocessors" not in opts or not any(p["key"] == "FFmpegExtractAudio" for p in opts.get("postprocessors", []))


def test_downloader_build_ydl_opts_m4a():
    cfg = AppConfig(
        audio_format="m4a",
        embed_artwork=True,
        embed_metadata=True,
    )
    downloader = YTMusicDownloader(cfg)
    opts = downloader._build_ydl_opts("out.m4a", lambda d: None, lambda d: None)

    extract_pp = next(p for p in opts["postprocessors"] if p["key"] == "FFmpegExtractAudio")
    assert extract_pp["preferredcodec"] == "m4a"
    assert extract_pp["preferredquality"] == "256"


def test_downloader_cancel_flag():
    cfg = AppConfig()
    downloader = YTMusicDownloader(cfg)
    assert not downloader._cancel_requested
    downloader.cancel()
    assert downloader._cancel_requested
    downloader.reset_cancel()
    assert not downloader._cancel_requested
