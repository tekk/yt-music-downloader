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


def test_fetch_user_playlists_no_cookies(tmp_path):
    cfg = AppConfig(cookies_path=str(tmp_path / "nonexistent_cookies.txt"))
    downloader = YTMusicDownloader(cfg)
    with pytest.raises(ValueError, match="cookies"):
        downloader.fetch_user_playlists()


def test_fetch_user_playlists_parsing(tmp_path, monkeypatch):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsome_value\n")
    cfg = AppConfig(cookies_path=str(cookie_file))
    downloader = YTMusicDownloader(cfg)

    mock_feed = {
        "entries": [
            {
                "id": "PL123",
                "title": "Chill Vibes",
                "url": "https://www.youtube.com/playlist?list=PL123",
                "playlist_count": 25,
                "uploader": "Test Channel",
            },
            {
                "id": "PL456",
                "title": "Workout Hits",
                "url": "https://music.youtube.com/playlist?list=PL456",
                "item_count": 10,
                "channel": "My Account",
            },
        ]
    }

    class MockYDL:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def extract_info(self, url, download=False):
            return mock_feed

    monkeypatch.setattr("yt_dlp.YoutubeDL", MockYDL)

    playlists = downloader.fetch_user_playlists()
    assert len(playlists) == 3  # Prepend LM + 2 user playlists
    assert playlists[0].id == "LM"
    assert "Liked Music" in playlists[0].title
    assert playlists[1].id == "PL123"
    assert playlists[1].title == "Chill Vibes"
    assert playlists[1].track_count == 25
    assert "music.youtube.com" in playlists[1].url
    assert playlists[2].id == "PL456"
    assert playlists[2].track_count == 10


def test_sanitize_filename_component():
    from yt_music_downloader.downloader import sanitize_filename_component

    assert sanitize_filename_component("AC/DC") == "AC-DC"
    assert sanitize_filename_component("What Is Love?") == "What Is Love"
    assert sanitize_filename_component('Artist: "Song" <Live>') == "Artist Song Live"
    assert sanitize_filename_component("  Multiple   Spaces  ") == "Multiple Spaces"
    assert sanitize_filename_component("...Leading and Trailing...") == "Leading and Trailing"
    assert sanitize_filename_component("") == "Unknown"


def test_extract_artist_and_title_multi_artists():
    from yt_music_downloader.downloader import extract_artist_and_title

    info = {
        "artists": ["Daft Punk", "Pharrell Williams"],
        "track": "Get Lucky",
        "title": "Get Lucky (Official Audio)",
    }
    artist, title = extract_artist_and_title(info)
    assert artist == "Daft Punk, Pharrell Williams"
    assert title == "Get Lucky"


def test_extract_artist_and_title_creators_and_duplicate_prefix():
    from yt_music_downloader.downloader import extract_artist_and_title

    info = {
        "creators": ["Shakira", "Burna Boy", "FIFA"],
        "title": "Shakira, Burna Boy - Dai Dai (Official Video)",
        "uploader": "Shakira",
    }
    artist, title = extract_artist_and_title(info)
    assert artist == "Shakira, Burna Boy, FIFA"
    assert title == "Dai Dai (Official Video)"


def test_extract_artist_and_title_topic_channel():
    from yt_music_downloader.downloader import extract_artist_and_title

    info = {
        "channel": "Rick Astley - Topic",
        "title": "Never Gonna Give You Up",
    }
    artist, title = extract_artist_and_title(info)
    assert artist == "Rick Astley"
    assert title == "Never Gonna Give You Up"


def test_extract_artist_and_title_split_title():
    from yt_music_downloader.downloader import extract_artist_and_title

    # Title with standard hyphen
    info1 = {
        "uploader": "Music Channel",
        "title": "Queen - Bohemian Rhapsody",
    }
    artist1, title1 = extract_artist_and_title(info1)
    assert artist1 == "Queen"
    assert title1 == "Bohemian Rhapsody"

    # Title with en-dash
    info2 = {
        "uploader": "Music Channel",
        "title": "Linkin Park – In The End",
    }
    artist2, title2 = extract_artist_and_title(info2)
    assert artist2 == "Linkin Park"
    assert title2 == "In The End"


def test_clean_metadata_pp_and_filename_template():
    import yt_dlp
    from yt_music_downloader.downloader import CleanMetadataPP, SONG_FILENAME_TEMPLATE

    ydl = yt_dlp.YoutubeDL({"outtmpl": SONG_FILENAME_TEMPLATE, "simulate": True})

    discovered = []
    pp = CleanMetadataPP(
        ydl,
        default_artist="Coldplay",
        default_title="Yellow",
        on_metadata_discovered=lambda a, t: discovered.append((a, t)),
    )
    ydl.add_post_processor(pp, when="pre_process")

    info = {
        "id": "vid123",
        "artists": ["Coldplay", "BTS"],
        "track": "My Universe",
        "title": "Coldplay, BTS - My Universe (Official Music Video)",
        "formats": [{"format_id": "1", "url": "https://example.com/audio.mp3", "ext": "mp3"}],
        "extractor": "generic",
    }
    res = ydl.process_ie_result(info, download=False)
    filename = ydl.prepare_filename(res)

    assert filename == "Coldplay, BTS - My Universe.mp3"
    assert res.get("artist") == "Coldplay, BTS"
    assert res.get("track") == "My Universe"
    assert len(discovered) == 1
    assert discovered[0] == ("Coldplay, BTS", "My Universe")


def test_fetch_info_uses_clean_artist_and_title(monkeypatch):
    cfg = AppConfig()
    downloader = YTMusicDownloader(cfg)

    mock_playlist = {
        "_type": "playlist",
        "title": "Sample Playlist",
        "uploader": "Curator",
        "entries": [
            {
                "id": "track1",
                "artists": ["Daft Punk"],
                "track": "One More Time",
                "title": "Daft Punk - One More Time",
                "duration": 320,
            },
            {
                "id": "track2",
                "channel": "Rick Astley - Topic",
                "title": "Never Gonna Give You Up",
                "duration": 213,
            },
            {
                "id": "track3",
                "title": "Calvin Harris ft. Dua Lipa - One Kiss",
                "uploader": "CalvinHarrisVEVO",
                "duration": 214,
            },
        ],
    }

    class MockYDL:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def extract_info(self, url, download=False):
            return mock_playlist

    monkeypatch.setattr("yt_dlp.YoutubeDL", MockYDL)

    info = downloader.fetch_info("https://music.youtube.com/playlist?list=PLtest")
    assert info.is_playlist is True
    assert len(info.tracks) == 3

    assert info.tracks[0].artist == "Daft Punk"
    assert info.tracks[0].title == "One More Time"

    assert info.tracks[1].artist == "Rick Astley"
    assert info.tracks[1].title == "Never Gonna Give You Up"

    assert info.tracks[2].artist == "Calvin Harris ft. Dua Lipa"
    assert info.tracks[2].title == "One Kiss"


def test_is_track_already_downloaded(tmp_path):
    from yt_music_downloader.downloader import TrackInfo, is_track_already_downloaded

    track = TrackInfo(index=1, artist="Daft Punk", title="Get Lucky")

    # 1. Directory doesn't exist
    assert is_track_already_downloaded(track, tmp_path / "nonexistent") is False

    # 2. File doesn't exist yet
    assert is_track_already_downloaded(track, tmp_path) is False

    # 3. 0-byte file (incomplete)
    zero_file = tmp_path / "Daft Punk - Get Lucky.mp3"
    zero_file.touch()
    assert is_track_already_downloaded(track, tmp_path, "mp3") is False

    # 4. Valid non-empty file
    zero_file.write_text("dummy audio data")
    assert is_track_already_downloaded(track, tmp_path, "mp3") is True

    # 5. Incomplete with active .part file
    part_file = tmp_path / "Daft Punk - Get Lucky.mp3.part"
    part_file.write_text("in progress")
    assert is_track_already_downloaded(track, tmp_path, "mp3") is False
    part_file.unlink()

    # 6. Different valid audio extension (e.g. .m4a or .flac)
    zero_file.unlink()
    flac_file = tmp_path / "Daft Punk - Get Lucky.flac"
    flac_file.write_text("dummy flac data")
    assert is_track_already_downloaded(track, tmp_path) is True


def test_check_existing_tracks_marking(tmp_path):
    from yt_music_downloader.config import AppConfig
    from yt_music_downloader.downloader import PlaylistInfo, TrackInfo, YTMusicDownloader

    cfg = AppConfig(download_dir=str(tmp_path), auto_create_playlist_folder=False)
    downloader = YTMusicDownloader(cfg)

    # Pre-create file for track 1
    (tmp_path / "Artist 1 - Song 1.mp3").write_text("audio")

    playlist = PlaylistInfo(
        title="Test Playlist",
        author="Curator",
        url="https://music.youtube.com/playlist?list=PL1",
        is_playlist=True,
        track_count=2,
        tracks=[
            TrackInfo(index=1, artist="Artist 1", title="Song 1"),
            TrackInfo(index=2, artist="Artist 2", title="Song 2"),
        ],
    )

    count = downloader.check_existing_tracks(playlist)
    assert count == 1
    assert playlist.tracks[0].status == "Done"
    assert playlist.tracks[0].percent == 100.0
    assert playlist.tracks[1].status == "Pending"


def test_download_playlist_skips_done_tracks(tmp_path, monkeypatch):
    from yt_music_downloader.config import AppConfig
    from yt_music_downloader.downloader import PlaylistInfo, TrackInfo, YTMusicDownloader

    cfg = AppConfig(download_dir=str(tmp_path), auto_create_playlist_folder=False)
    downloader = YTMusicDownloader(cfg)

    # Track 1 is already Done; Track 2 is Pending
    t1 = TrackInfo(index=1, artist="Artist 1", title="Song 1", status="Done", percent=100.0, url="https://yt.com/1")
    t2 = TrackInfo(index=2, artist="Artist 2", title="Song 2", status="Pending", percent=0.0, url="https://yt.com/2")

    playlist = PlaylistInfo(
        title="Test Playlist",
        author="Curator",
        url="https://music.youtube.com/playlist?list=PL1",
        is_playlist=True,
        track_count=2,
        tracks=[t1, t2],
    )

    downloaded_urls = []

    class MockYDL:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def add_post_processor(self, *args, **kwargs):
            pass
        def download(self, urls):
            downloaded_urls.extend(urls)

    monkeypatch.setattr("yt_dlp.YoutubeDL", MockYDL)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/ffmpeg")

    logs = []
    downloader.download_playlist(
        playlist=playlist,
        on_track_update=lambda t: None,
        on_progress_update=lambda p: None,
        on_log=lambda m: logs.append(m),
    )

    # Verify Track 1 was skipped and only Track 2 was downloaded
    assert downloaded_urls == ["https://yt.com/2"]
    assert t1.status == "Done"
    assert t2.status == "Done"
    assert any("Skipping already completed: Artist 1 - Song 1" in m for m in logs)


def test_download_playlist_all_done_returns_immediately(tmp_path, monkeypatch):
    from yt_music_downloader.config import AppConfig
    from yt_music_downloader.downloader import PlaylistInfo, TrackInfo, YTMusicDownloader

    cfg = AppConfig(download_dir=str(tmp_path), auto_create_playlist_folder=False)
    downloader = YTMusicDownloader(cfg)

    t1 = TrackInfo(index=1, artist="Artist 1", title="Song 1", status="Done", percent=100.0)
    playlist = PlaylistInfo(
        title="Test Playlist",
        author="Curator",
        url="https://music.youtube.com/playlist?list=PL1",
        is_playlist=True,
        track_count=1,
        tracks=[t1],
    )

    download_called = False

    class MockYDL:
        def __init__(self, *args, **kwargs):
            pass
        def download(self, urls):
            nonlocal download_called
            download_called = True

    monkeypatch.setattr("yt_dlp.YoutubeDL", MockYDL)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/ffmpeg")

    logs = []
    downloader.download_playlist(
        playlist=playlist,
        on_track_update=lambda t: None,
        on_progress_update=lambda p: None,
        on_log=lambda m: logs.append(m),
    )

    assert download_called is False
    assert any("already downloaded" in m for m in logs)


