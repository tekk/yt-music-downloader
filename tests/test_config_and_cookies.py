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


def test_is_yt_cookie():
    from yt_music_downloader.browser_auth import is_yt_cookie

    # Allowed YouTube domains
    assert is_yt_cookie(".youtube.com", "LOGIN_INFO")
    assert is_yt_cookie("youtube.com", "SID")
    assert is_yt_cookie(".music.youtube.com", "PREF")
    assert is_yt_cookie("www.youtube.com", "YSC")
    assert is_yt_cookie(".youtubekids.com", "GPS")

    # Allowed Google auth domains and cookies
    assert is_yt_cookie(".google.com", "SAPISID")
    assert is_yt_cookie(".google.com", "__Secure-1PSID")
    assert is_yt_cookie("google.com", "__Secure-3PAPISID")
    assert is_yt_cookie("accounts.google.com", "ACCOUNT_CHOOSER")
    assert is_yt_cookie("accounts.google.com", "LSID")

    # Disallowed non-YouTube Google subdomains
    assert not is_yt_cookie("mail.google.com", "GMAIL_AT")
    assert not is_yt_cookie("drive.google.com", "session")
    assert not is_yt_cookie("docs.google.com", "token")
    assert not is_yt_cookie("calendar.google.com", "cal_id")

    # Disallowed tracking / unrelated cookies on google.com
    assert not is_yt_cookie(".google.com", "_ga")
    assert not is_yt_cookie(".google.com", "_ga_12345")
    assert not is_yt_cookie(".google.com", "AEC")
    assert not is_yt_cookie(".google.com", "SEARCH_SAMESITE")

    # Disallowed external third-party domains
    assert not is_yt_cookie(".tatrabanka.sk", "session")
    assert not is_yt_cookie("example.com", "token")
    assert not is_yt_cookie(".facebook.com", "c_user")
    assert not is_yt_cookie(".adnxs.com", "uuid2")


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

    # With only_yt_needed=True (default), example.com is filtered out
    filtered_content = format_cookies_to_netscape(sample_cookies, only_yt_needed=True)
    filtered_lines = [l for l in filtered_content.splitlines() if l and not l.startswith("#")]
    assert len(filtered_lines) == 2

    # With only_yt_needed=False, all 3 cookies are kept
    all_content = format_cookies_to_netscape(sample_cookies, only_yt_needed=False)
    all_lines = [l for l in all_content.splitlines() if l and not l.startswith("#")]
    assert len(all_lines) == 3

    # Check YouTube SID line
    sid_line = filtered_lines[0].split("\t")
    assert sid_line[0] == ".youtube.com"
    assert sid_line[1] == "TRUE"
    assert sid_line[2] == "/"
    assert sid_line[3] == "TRUE"
    assert sid_line[4] == "1893456000"
    assert sid_line[5] == "SID"
    assert sid_line[6] == "secret_sid_val"


def test_import_and_filter_cookie_file(tmp_path):
    from yt_music_downloader.browser_auth import import_and_filter_cookie_file

    src_file = tmp_path / "raw_cookies.txt"
    dst_file = tmp_path / "clean_cookies.txt"

    content = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsample_sid\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tLOGIN_INFO\tsample_login\n"
        ".google.com\tTRUE\t/\tTRUE\t2147483647\t__Secure-3PSID\tsecure_sid\n"
        ".google.com\tTRUE\t/\tTRUE\t2147483647\t_ga\tunneeded_ga\n"
        ".bank.com\tTRUE\t/\tTRUE\t2147483647\tbanking_auth\tprivate_session\n"
    )
    src_file.write_text(content, encoding="utf-8")

    status, discarded = import_and_filter_cookie_file(src_file, dst_file)
    assert status.exists
    assert status.is_authenticated
    assert status.count == 3
    assert discarded == 2

    # Verify destination file content contains ONLY the 3 YT-relevant cookies
    dst_lines = [l for l in dst_file.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    assert len(dst_lines) == 3
    domains = [l.split("\t")[0] for l in dst_lines]
    names = [l.split("\t")[5] for l in dst_lines]
    assert ".bank.com" not in domains
    assert "_ga" not in names
    assert "SID" in names
    assert "LOGIN_INFO" in names
    assert "__Secure-3PSID" in names


def test_sanitize_cookie_file(tmp_path):
    from yt_music_downloader.browser_auth import sanitize_cookie_file

    cookie_file = tmp_path / "test_cookies.txt"
    content = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsample_sid\n"
        ".shop.com\tTRUE\t/\tTRUE\t2147483647\tcart\tval\n"
    )
    cookie_file.write_text(content, encoding="utf-8")

    kept, discarded = sanitize_cookie_file(cookie_file)
    assert kept == 1
    assert discarded == 1

    lines = [l for l in cookie_file.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    assert len(lines) == 1
    assert lines[0].split("\t")[5] == "SID"


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


def test_extract_from_installed_browser_filtering(tmp_path, monkeypatch):
    import yt_dlp.cookies
    from http.cookiejar import Cookie
    from yt_music_downloader.browser_auth import extract_from_installed_browser

    mock_jar = yt_dlp.cookies.YoutubeDLCookieJar()
    c1 = Cookie(0, "LOGIN_INFO", "token", None, False, ".youtube.com", True, False, "/", True, False, 2000000000, False, None, None, {})
    c2 = Cookie(0, "personal_session", "secret", None, False, ".otherbank.com", True, False, "/", True, False, 2000000000, False, None, None, {})
    mock_jar.set_cookie(c1)
    mock_jar.set_cookie(c2)

    monkeypatch.setattr(yt_dlp.cookies, "extract_cookies_from_browser", lambda b: mock_jar)

    out_file = tmp_path / "browser_clean.txt"
    status = extract_from_installed_browser("chrome", out_file)

    assert status.exists
    assert status.is_authenticated
    assert status.count == 1
    assert "LOGIN_INFO" in status.auth_cookies

    content = out_file.read_text(encoding="utf-8")
    assert ".otherbank.com" not in content
    assert ".youtube.com" in content
