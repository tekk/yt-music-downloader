"""Unit tests for configuration and cookie management."""

import tempfile
from pathlib import Path
import pytest

from yt_music_downloader.config import AppConfig, get_default_music_dir
from yt_music_downloader.browser_auth import (
    AUTH_COOKIE_NAMES,
    check_cookie_file,
    detect_system_chromium,
    format_cookies_to_netscape,
)


def test_config_defaults_and_save_load(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg = AppConfig(download_dir=str(tmp_path / "music"), audio_format="m4a")
    
    # Override path for testing
    AppConfig.config_file_path = classmethod(lambda cls: cfg_file)
    cfg.save()

    assert cfg_file.is_file()
    loaded = AppConfig.load()
    assert loaded.audio_format == "m4a"
    assert loaded.download_dir == str(tmp_path / "music")
    assert loaded.theme == "textual-dark"
    assert loaded.embed_artwork is True
    assert loaded.embed_metadata is True


def test_format_cookies_to_netscape():
    sample_cookies = [
        {
            "name": "SID",
            "value": "secret_sid_val",
            "domain": ".youtube.com",
            "path": "/",
            "expires": 1893456000,
            "secure": True,
        },
        {
            "name": "LOGIN_INFO",
            "value": "login_token_abc",
            "domain": ".youtube.com",
            "path": "/",
            "expires": -1,
            "secure": True,
        },
        {
            "name": "other",
            "value": "val",
            "domain": "example.com",
            "path": "/sub",
            "expires": 0,
            "secure": False,
        }
    ]

    netscape_content = format_cookies_to_netscape(sample_cookies)
    lines = [l for l in netscape_content.splitlines() if l and not l.startswith("#")]
    assert len(lines) == 3

    # Check YouTube SID line
    sid_line = lines[0].split("\t")
    assert sid_line[0] == ".youtube.com"
    assert sid_line[1] == "TRUE"
    assert sid_line[2] == "/"
    assert sid_line[3] == "TRUE"
    assert sid_line[4] == "1893456000"
    assert sid_line[5] == "SID"
    assert sid_line[6] == "secret_sid_val"


def test_check_cookie_file(tmp_path):
    cookie_file = tmp_path / "cookies.txt"
    
    # Non-existent
    status_empty = check_cookie_file(cookie_file)
    assert not status_empty.exists
    assert not status_empty.is_authenticated

    # Write auth cookies
    content = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsample_sid\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tLOGIN_INFO\tsample_login\n"
    )
    cookie_file.write_text(content, encoding="utf-8")

    status = check_cookie_file(cookie_file)
    assert status.exists
    assert status.has_youtube
    assert status.is_authenticated
    assert status.count == 2
    assert "SID" in status.auth_cookies
    assert "LOGIN_INFO" in status.auth_cookies


def test_detect_system_chromium():
    # Should return string or None without crashing
    path = detect_system_chromium()
    if path is not None:
        assert isinstance(path, str)
        assert Path(path).is_file()
