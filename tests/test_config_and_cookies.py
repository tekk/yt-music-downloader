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

    # Allowed YouTube domains & necessary cookies
    assert is_yt_cookie(".youtube.com", "LOGIN_INFO")
    assert is_yt_cookie("youtube.com", "SID")
    assert is_yt_cookie(".music.youtube.com", "PREF")
    assert is_yt_cookie("www.youtube.com", "YSC")
    assert is_yt_cookie(".youtubekids.com", "GPS")
    assert is_yt_cookie(".youtube.com", "VISITOR_INFO1_LIVE")
    assert is_yt_cookie(".youtube.com", "VISITOR_PRIVACY_METADATA")
    assert is_yt_cookie(".youtube.com", "__Secure-YEC")
    assert is_yt_cookie(".youtube.com", "__Secure-YENID")
    assert is_yt_cookie(".youtube.com", "__Secure-ROLLOUT_TOKEN")
    assert is_yt_cookie(".youtube.com", "__Secure-1PSIDTS")
    assert is_yt_cookie(".youtube.com", "__Secure-3PSIDTS")
    assert is_yt_cookie(".youtube.com", "SOCS")
    assert is_yt_cookie(".youtube.com", "CONSENT")

    # Disallowed non-essential cookies on YouTube domains (analytics, ads, search tracking)
    assert not is_yt_cookie(".youtube.com", "_ga")
    assert not is_yt_cookie(".youtube.com", "_gid")
    assert not is_yt_cookie(".youtube.com", "_gat")
    assert not is_yt_cookie(".youtube.com", "_gcl_au")
    assert not is_yt_cookie(".youtube.com", "IDE")
    assert not is_yt_cookie(".youtube.com", "1P_JAR")
    assert not is_yt_cookie(".youtube.com", "NID")
    assert not is_yt_cookie(".youtube.com", "AEC")
    assert not is_yt_cookie(".youtube.com", "FCCDCF")
    assert not is_yt_cookie("music.youtube.com", "random_tracker")

    # Allowed Google auth domains and necessary identity cookies
    assert is_yt_cookie(".google.com", "SAPISID")
    assert is_yt_cookie(".google.com", "__Secure-1PSID")
    assert is_yt_cookie("google.com", "__Secure-3PAPISID")
    assert is_yt_cookie(".google.com", "__Secure-1PSIDTS")
    assert is_yt_cookie(".google.com", "__Secure-3PSIDTS")
    assert is_yt_cookie("accounts.google.com", "ACCOUNT_CHOOSER")
    assert is_yt_cookie("accounts.google.com", "LSID")

    # Disallowed non-YouTube Google services cookies on google.com
    assert not is_yt_cookie(".google.com", "__Secure-OSID")
    assert not is_yt_cookie(".google.com", "__Secure-ENID")
    assert not is_yt_cookie(".google.com", "__Secure-PAY-TOKEN")
    assert not is_yt_cookie(".google.com", "__Secure-WALLET-AUTH")
    assert not is_yt_cookie(".google.com", "COMPASS")
    assert not is_yt_cookie(".google.com", "DRIVE_STREAM_VERSION")

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
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\t_ga\tyoutube_ga_tracker\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tIDE\tdoubleclick_ad\n"
        ".google.com\tTRUE\t/\tTRUE\t2147483647\t__Secure-3PSID\tsecure_sid\n"
        ".google.com\tTRUE\t/\tTRUE\t2147483647\t__Secure-OSID\tdocs_drive_session\n"
        ".google.com\tTRUE\t/\tTRUE\t2147483647\t__Secure-PAY-AUTH\tgoogle_pay\n"
        ".google.com\tTRUE\t/\tTRUE\t2147483647\tNID\tgoogle_search_nid\n"
        ".google.com\tTRUE\t/\tTRUE\t2147483647\t_ga\tunneeded_ga\n"
        ".bank.com\tTRUE\t/\tTRUE\t2147483647\tbanking_auth\tprivate_session\n"
    )
    src_file.write_text(content, encoding="utf-8")

    status, discarded = import_and_filter_cookie_file(src_file, dst_file)
    assert status.exists
    assert status.is_authenticated
    assert status.count == 3
    assert discarded == 7
    assert status.discarded == 7

    # Verify destination file content contains ONLY the 3 YT-relevant cookies
    dst_lines = [l for l in dst_file.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    assert len(dst_lines) == 3
    domains = [l.split("\t")[0] for l in dst_lines]
    names = [l.split("\t")[5] for l in dst_lines]
    assert ".bank.com" not in domains
    assert "_ga" not in names
    assert "IDE" not in names
    assert "__Secure-OSID" not in names
    assert "__Secure-PAY-AUTH" not in names
    assert "NID" not in names
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
    # Necessary YouTube cookies
    c1 = Cookie(0, "LOGIN_INFO", "token", None, False, ".youtube.com", True, False, "/", True, False, 2000000000, False, None, None, {})
    c2 = Cookie(0, "PREF", "f6=400", None, False, ".music.youtube.com", True, False, "/", True, False, 2000000000, False, None, None, {})
    c3 = Cookie(0, "SAPISID", "sapisid_secret", None, False, ".google.com", True, False, "/", True, False, 2000000000, False, None, None, {})
    # Unrelated browser / tracking cookies
    c4 = Cookie(0, "personal_session", "secret", None, False, ".otherbank.com", True, False, "/", True, False, 2000000000, False, None, None, {})
    c5 = Cookie(0, "_ga", "analytics", None, False, ".youtube.com", True, False, "/", True, False, 2000000000, False, None, None, {})
    c6 = Cookie(0, "IDE", "doubleclick", None, False, ".youtube.com", True, False, "/", True, False, 2000000000, False, None, None, {})
    c7 = Cookie(0, "__Secure-OSID", "docs_session", None, False, ".google.com", True, False, "/", True, False, 2000000000, False, None, None, {})
    c8 = Cookie(0, "NID", "search_pref", None, False, ".google.com", True, False, "/", True, False, 2000000000, False, None, None, {})

    for c in (c1, c2, c3, c4, c5, c6, c7, c8):
        mock_jar.set_cookie(c)

    monkeypatch.setattr(yt_dlp.cookies, "extract_cookies_from_browser", lambda b: mock_jar)

    out_file = tmp_path / "browser_clean.txt"
    status = extract_from_installed_browser("chrome", out_file)

    assert status.exists
    assert status.is_authenticated
    assert status.count == 3
    assert status.discarded == 5
    assert "LOGIN_INFO" in status.auth_cookies
    assert "SAPISID" in status.auth_cookies

    content = out_file.read_text(encoding="utf-8")
    assert ".otherbank.com" not in content
    assert "_ga" not in content
    assert "IDE" not in content
    assert "__Secure-OSID" not in content
    assert "NID" not in content
    assert "LOGIN_INFO" in content
    assert "PREF" in content
    assert "SAPISID" in content


def test_has_cookies_status(tmp_path):
    cookie_path = tmp_path / "test_cookies.txt"
    cfg = AppConfig(cookies_path=str(cookie_path))

    # File does not exist
    assert not cfg.has_cookies()

    # Empty file
    cookie_path.write_text("", encoding="utf-8")
    assert not cfg.has_cookies()

    # Non-empty file
    cookie_path.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    assert cfg.has_cookies()


def test_config_load_invalid_json(tmp_path):
    cfg_file = tmp_path / "corrupted_config.json"
    cfg_file.write_text("NOT VALID JSON! {", encoding="utf-8")

    AppConfig.config_file_path = classmethod(lambda cls: cfg_file)
    cfg = AppConfig.load()
    # Falls back to default config without crashing
    assert cfg.audio_format == "mp3"
    assert cfg.mp3_quality == "320"


def test_get_default_music_dir_fallback(monkeypatch):
    import platformdirs
    monkeypatch.setattr(platformdirs, "user_music_dir", lambda: (_ for _ in ()).throw(RuntimeError("OS error")))
    music_dir = get_default_music_dir()
    assert "YT-Music" in str(music_dir)


def test_get_browser_profile_dir():
    from yt_music_downloader.config import get_browser_profile_dir
    p = get_browser_profile_dir()
    assert p.is_dir()
    assert "browser_profile" in str(p)


def test_check_cookie_file_counts_only_valid_yt_cookies(tmp_path):
    cookie_file = tmp_path / "mixed_cookies.txt"
    content = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tLOGIN_INFO\tsample_login\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tPREF\tf6=400\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\t_ga\tunneeded_ga\n"
        ".google.com\tTRUE\t/\tTRUE\t2147483647\t__Secure-OSID\tunneeded_osid\n"
        ".bank.com\tTRUE\t/\tTRUE\t2147483647\tbanking_auth\tprivate_session\n"
    )
    cookie_file.write_text(content, encoding="utf-8")

    # When sanitize=False, count should only count the 2 valid YouTube cookies
    status_raw = check_cookie_file(cookie_file, sanitize=False)
    assert status_raw.exists
    assert status_raw.count == 2
    assert status_raw.is_authenticated
    assert status_raw.auth_cookies == ["LOGIN_INFO"]

    # When sanitize=True, file is cleaned in place and discarded count is reported
    status_clean = check_cookie_file(cookie_file, sanitize=True)
    assert status_clean.exists
    assert status_clean.count == 2
    assert status_clean.discarded == 3
    remaining_lines = [l for l in cookie_file.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    assert len(remaining_lines) == 2


def test_import_only_unrelated_cookies(tmp_path):
    from yt_music_downloader.browser_auth import import_and_filter_cookie_file

    src_file = tmp_path / "other_cookies.txt"
    dst_file = tmp_path / "clean.txt"
    content = (
        "# Netscape HTTP Cookie File\n"
        ".facebook.com\tTRUE\t/\tTRUE\t2147483647\tc_user\t12345\n"
        ".google.com\tTRUE\t/\tTRUE\t2147483647\tNID\tgoogle_search\n"
        ".amazon.com\tTRUE\t/\tTRUE\t2147483647\tsession-id\t98765\n"
    )
    src_file.write_text(content, encoding="utf-8")

    status, discarded = import_and_filter_cookie_file(src_file, dst_file)
    assert not status.exists
    assert status.count == 0
    assert not status.is_authenticated
    assert discarded == 3
    assert status.discarded == 3
    assert not dst_file.exists()


