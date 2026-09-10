"""Browser launch and cookie capture management for YouTube Music authentication."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import urllib.request

import websockets
import yt_dlp.cookies

from .config import get_app_dir, get_browser_profile_dir, get_default_cookies_path

logger = logging.getLogger(__name__)

# Key auth cookies indicating successful Google/YouTube Music login
AUTH_COOKIE_NAMES = {
    "LOGIN_INFO",
    "SAPISID",
    "SID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "__Secure-1PAPISID",
    "__Secure-3PAPISID",
    "SSID",
    "APISID",
}

# Allowed YouTube domain suffixes
YT_DOMAINS = {
    "youtube.com",
    "music.youtube.com",
    "youtubekids.com",
}

# Domains under Google allowed for YouTube/Google identity authentication
GOOGLE_AUTH_DOMAINS = {
    "google.com",
    "accounts.google.com",
    "apis.google.com",
    "myaccount.google.com",
}

# Necessary Google auth/session cookies for YouTube Innertube / Identity
GOOGLE_AUTH_COOKIE_NAMES = {
    "LOGIN_INFO",
    "SAPISID",
    "SID",
    "SSID",
    "HSID",
    "APISID",
    "SIDCC",
    "PREF",
    "SOCS",
    "YSC",
    "GPS",
    "VISITOR_INFO1_LIVE",
    "VISITOR_PRIVACY_METADATA",
    "ACCOUNT_CHOOSER",
    "LSID",
    "__Host-1PLSID",
    "__Host-3PLSID",
    "__Host-GAPS",
}

GOOGLE_AUTH_PREFIXES = (
    "__Secure-",
)


def is_yt_cookie(domain: str, name: str) -> bool:
    """Return True only if cookie is necessary for YouTube / YouTube Music functionality."""
    if not domain or not name:
        return False
    d = domain.lstrip(".").lower()

    # 1. YouTube domains: include all cookies set specifically for YouTube
    for yt_d in YT_DOMAINS:
        if d == yt_d or d.endswith("." + yt_d):
            return True

    # 2. Google Identity domains: include only necessary authentication tokens
    if d in GOOGLE_AUTH_DOMAINS:
        if name in GOOGLE_AUTH_COOKIE_NAMES or name.startswith(GOOGLE_AUTH_PREFIXES):
            return True

    return False


@dataclass
class CookieStatus:
    exists: bool = False
    count: int = 0
    has_youtube: bool = False
    is_authenticated: bool = False
    auth_cookies: list[str] = None
    file_path: str = ""

    def __post_init__(self):
        if self.auth_cookies is None:
            self.auth_cookies = []


def find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def detect_system_chromium() -> Optional[str]:
    """Find installed Chromium-based browser executable across macOS, Windows, and Linux."""
    os_name = platform.system()

    if os_name == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        ]
        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

    elif os_name == "Windows":
        roots = [
            os.environ.get("LOCALAPPDATA", ""),
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMFILES(X86)", ""),
        ]
        suffixes = [
            r"Google\Chrome\Application\chrome.exe",
            r"Microsoft\Edge\Application\msedge.exe",
            r"BraveSoftware\Brave-Browser\Application\brave.exe",
            r"Chromium\Application\chrome.exe",
        ]
        for root in roots:
            if not root:
                continue
            for suffix in suffixes:
                full_path = os.path.join(root, suffix)
                if os.path.isfile(full_path):
                    return full_path

    else:  # Linux / BSD
        binaries = [
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "brave-browser",
            "microsoft-edge",
            "microsoft-edge-stable",
        ]
        for b in binaries:
            path = shutil.which(b)
            if path:
                return path

    return None


def format_cookies_to_netscape(cookies: list[dict], only_yt_needed: bool = True) -> str:
    """Format CDP or dictionary cookies into standard Netscape cookies.txt format.
    
    If only_yt_needed is True, only cookies needed for YouTube/YouTube Music are included.
    """
    lines = [
        "# Netscape HTTP Cookie File",
        "# http://curl.haxx.se/rfc/cookie_spec.html",
        "# This file is generated by YT Music Downloader. Do not edit manually.",
        "",
    ]
    for c in cookies:
        domain = c.get("domain", "")
        name = c.get("name", "")
        if not domain or not name:
            continue
        if only_yt_needed and not is_yt_cookie(domain, name):
            continue

        include_sub = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure", False) else "FALSE"
        
        # Expiry time (unix timestamp in seconds)
        exp = c.get("expires", 0)
        if exp and exp > 0:
            expires_str = str(int(exp))
        else:
            expires_str = "0"

        value = c.get("value", "")
        lines.append(f"{domain}\t{include_sub}\t{path}\t{secure}\t{expires_str}\t{name}\t{value}")

    return "\n".join(lines) + "\n"


def filter_cookie_lines(lines: list[str]) -> tuple[list[str], int]:
    """Filter Netscape cookie format lines to only keep cookies needed for YouTube / YouTube Music.
    
    Returns:
        tuple[list[str], int]: (filtered_lines, discarded_count)
    """
    kept_lines: list[str] = []
    discarded_count = 0

    has_header = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if kept_lines and kept_lines[-1] != "":
                kept_lines.append("")
            continue
        if stripped.startswith("#"):
            if "Netscape HTTP Cookie File" in stripped:
                has_header = True
            kept_lines.append(stripped)
            continue

        parts = stripped.split("\t")
        if len(parts) >= 7:
            domain = parts[0]
            name = parts[5]
            if is_yt_cookie(domain, name):
                kept_lines.append(stripped)
            else:
                discarded_count += 1
        else:
            # Non-cookie or malformed data line
            discarded_count += 1

    if not has_header:
        kept_lines.insert(0, "# Netscape HTTP Cookie File")
        kept_lines.insert(1, "# Filtered for YouTube / YouTube Music functionality")

    return kept_lines, discarded_count


def sanitize_cookie_file(cookie_path: str | Path) -> tuple[int, int]:
    """In-place sanitize a cookies file, stripping any cookies unrelated to YouTube / YouTube Music.
    
    Returns:
        tuple[int, int]: (kept_cookie_count, discarded_cookie_count)
    """
    path = Path(cookie_path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size == 0:
        return 0, 0

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        filtered_lines, discarded = filter_cookie_lines(lines)
        if discarded > 0:
            tmp_path = path.with_suffix(".sanitize.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write("\n".join(filtered_lines) + "\n")
            tmp_path.replace(path)
            logger.info(f"Sanitized {path.name}: removed {discarded} unrelated cookies.")

        data_count = sum(1 for l in filtered_lines if l and not l.startswith("#"))
        return data_count, discarded
    except Exception as e:
        logger.warning(f"Failed to sanitize cookie file {path}: {e}")
        return 0, 0


def import_and_filter_cookie_file(
    source_path: str | Path,
    target_path: Optional[str | Path] = None,
) -> tuple[CookieStatus, int]:
    """Import a Netscape cookies.txt file, filtering out all non-YouTube/YouTube Music cookies.
    
    Args:
        source_path: Path to the input cookies file.
        target_path: Path to write filtered cookies (defaults to default app cookies path).
        
    Returns:
        tuple[CookieStatus, int]: (status of target file, count of discarded unrelated cookies)
    """
    src = Path(source_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Source cookie file does not exist: {src}")

    dst = Path(target_path or get_default_cookies_path()).expanduser().resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)

    with open(src, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    filtered_lines, discarded = filter_cookie_lines(lines)

    # Check how many data cookies were kept
    data_lines = [l for l in filtered_lines if l and not l.startswith("#")]
    if not data_lines:
        return CookieStatus(exists=False, file_path=str(dst)), discarded

    # Write to target destination atomically
    tmp_target = dst.with_suffix(".tmp")
    with open(tmp_target, "w", encoding="utf-8") as f:
        f.write("\n".join(filtered_lines) + "\n")
    tmp_target.replace(dst)

    status = check_cookie_file(dst, sanitize=False)
    return status, discarded


def check_cookie_file(cookie_path: str | Path, sanitize: bool = True) -> CookieStatus:
    """Check the status of an existing cookies file."""
    path = Path(cookie_path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size == 0:
        return CookieStatus(exists=False, file_path=str(path))

    if sanitize:
        sanitize_cookie_file(path)

    count = 0
    has_youtube = False
    found_auth = []

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    count += 1
                    domain, _, _, _, _, name, _ = parts[:7]
                    if is_yt_cookie(domain, name):
                        has_youtube = True
                        if name in AUTH_COOKIE_NAMES and name not in found_auth:
                            found_auth.append(name)
    except Exception as e:
        logger.warning(f"Error parsing cookies file {path}: {e}")

    return CookieStatus(
        exists=True,
        count=count,
        has_youtube=has_youtube,
        is_authenticated=len(found_auth) > 0,
        auth_cookies=found_auth,
        file_path=str(path),
    )


def extract_from_installed_browser(browser_name: str, output_path: str | Path) -> CookieStatus:
    """Extract cookies from an installed browser, keeping only cookies needed for YouTube / YouTube Music."""
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    jar = yt_dlp.cookies.extract_cookies_from_browser(browser_name)
    
    # Filter jar so only YouTube and essential Google auth cookies are saved
    filtered_jar = yt_dlp.cookies.YoutubeDLCookieJar(str(output_path))
    for cookie in jar:
        if is_yt_cookie(cookie.domain, cookie.name):
            filtered_jar.set_cookie(cookie)

    filtered_jar.save(ignore_discard=True, ignore_expires=True)
    return check_cookie_file(output_path, sanitize=False)


class BrowserLoginSession:
    """Manages launching a browser window and extracting session cookies via CDP."""

    def __init__(
        self,
        target_cookie_path: str | Path = None,
        on_status: Optional[Callable[[str], None]] = None,
    ):
        self.target_cookie_path = Path(target_cookie_path or get_default_cookies_path())
        self.on_status = on_status or (lambda _: None)
        self.process: Optional[subprocess.Popen] = None
        self.port: int = 0
        self.profile_dir: Path = get_browser_profile_dir()
        self._stop_event = asyncio.Event()

    def _notify(self, msg: str) -> None:
        self.on_status(msg)
        logger.info(msg)

    def launch_browser(self) -> bool:
        """Launch Chromium-based browser with dedicated profile and CDP port."""
        executable = detect_system_chromium()
        if not executable:
            self._notify("No compatible Chromium browser found (Chrome/Edge/Brave).")
            return False

        self.port = find_free_port()
        cmd = [
            executable,
            f"--user-data-dir={self.profile_dir}",
            f"--remote-debugging-port={self.port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-search-engine-choice-screen",
            "https://music.youtube.com",
        ]

        self._notify(f"Launching {Path(executable).stem} on port {self.port}...")
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            self._notify(f"Failed to launch browser: {e}")
            return False

    async def _get_cdp_ws_url(self) -> Optional[str]:
        """Query CDP JSON API to obtain the browser or page WebSocket URL."""
        url = f"http://127.0.0.1:{self.port}/json/version"
        loop = asyncio.get_running_loop()

        for _ in range(30):
            if self._stop_event.is_set():
                return None
            try:
                def fetch():
                    req = urllib.request.Request(url, headers={"User-Agent": "YT-Music-DL"})
                    with urllib.request.urlopen(req, timeout=1.0) as resp:
                        return json.loads(resp.read().decode("utf-8"))

                data = await loop.run_in_executor(None, fetch)
                ws_url = data.get("webSocketDebuggerUrl")
                if ws_url:
                    return ws_url
            except Exception:
                await asyncio.sleep(0.5)

        return None

    async def wait_for_login(self, timeout: int = 300) -> Optional[CookieStatus]:
        """Poll cookies from browser until login authentication cookies are detected."""
        ws_url = await self._get_cdp_ws_url()
        if not ws_url:
            self._notify("Could not establish connection to browser DevTools.")
            return None

        self._notify("Connected to browser! Please sign in to YouTube Music...")

        try:
            async with websockets.connect(ws_url) as ws:
                start_time = asyncio.get_event_loop().time()
                req_id = 0

                while not self._stop_event.is_set():
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        self._notify("Login timed out after 5 minutes.")
                        break

                    req_id += 1
                    # Request all cookies from browser storage
                    await ws.send(json.dumps({
                        "id": req_id,
                        "method": "Storage.getCookies",
                    }))

                    # Wait for response with timeout
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        resp = json.loads(raw)
                        if resp.get("id") == req_id:
                            cookies = resp.get("result", {}).get("cookies", [])
                            yt_cookies = [
                                c for c in cookies
                                if is_yt_cookie(c.get("domain", ""), c.get("name", ""))
                            ]
                            
                            found_auth = [
                                c["name"] for c in yt_cookies
                                if c.get("name") in AUTH_COOKIE_NAMES
                            ]

                            if found_auth:
                                self._notify(f"Authentication detected ({', '.join(set(found_auth))})! Saving cookies...")
                                netscape_data = format_cookies_to_netscape(yt_cookies)
                                self.target_cookie_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(self.target_cookie_path, "w", encoding="utf-8") as f:
                                    f.write(netscape_data)

                                status = check_cookie_file(self.target_cookie_path)
                                self._notify(f"Success! {status.count} cookies saved to {self.target_cookie_path.name}.")
                                return status

                    except asyncio.TimeoutError:
                        pass

                    await asyncio.sleep(1.5)

        except Exception as e:
            self._notify(f"Browser communication error: {e}")

        return None

    def stop(self) -> None:
        """Signal poller to stop and close browser process."""
        self._stop_event.set()
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
