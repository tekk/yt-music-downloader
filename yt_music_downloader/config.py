"""Configuration and persistence management for YT Music Downloader."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
import platformdirs

APP_NAME = "yt-music-downloader"
APP_AUTHOR = "Tekk"


def get_default_music_dir() -> Path:
    """Get cross-platform default music download directory."""
    try:
        music_dir = platformdirs.user_music_dir()
        if music_dir:
            return Path(music_dir) / "YT-Music"
    except Exception:
        pass
    return Path.home() / "Music" / "YT-Music"


def get_app_dir() -> Path:
    """Get cross-platform config and data directory."""
    app_dir = Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_default_cookies_path() -> Path:
    """Get path to the app's default cookies.txt file."""
    return get_app_dir() / "cookies.txt"


def get_browser_profile_dir() -> Path:
    """Get path to the isolated browser profile directory used for authentication."""
    profile_dir = get_app_dir() / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


@dataclass
class AppConfig:
    """Application settings and state."""

    download_dir: str = field(default_factory=lambda: str(get_default_music_dir()))
    theme: str = "textual-dark"
    audio_format: str = "mp3"  # "original", "mp3", "m4a", "flac", "opus"
    mp3_quality: str = "320"  # "320", "256", "192", "0" (VBR best)
    embed_artwork: bool = True
    embed_metadata: bool = True
    cookies_path: str = field(default_factory=lambda: str(get_default_cookies_path()))
    auto_create_playlist_folder: bool = True

    @classmethod
    def config_file_path(cls) -> Path:
        return get_app_dir() / "config.json"

    @classmethod
    def load(cls) -> AppConfig:
        """Load configuration from JSON or return defaults."""
        path = cls.config_file_path()
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(
                    download_dir=data.get("download_dir", str(get_default_music_dir())),
                    theme=data.get("theme", "textual-dark"),
                    audio_format=data.get("audio_format", "mp3"),
                    mp3_quality=data.get("mp3_quality", "320"),
                    embed_artwork=data.get("embed_artwork", True),
                    embed_metadata=data.get("embed_metadata", True),
                    cookies_path=data.get("cookies_path", str(get_default_cookies_path())),
                    auto_create_playlist_folder=data.get("auto_create_playlist_folder", True),
                )
            except Exception:
                pass
        config = cls()
        config.save()
        return config

    def save(self) -> None:
        """Save configuration to JSON."""
        path = self.config_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    def has_cookies(self) -> bool:
        """Check whether a non-empty cookies file exists."""
        p = Path(self.cookies_path)
        return p.is_file() and p.stat().st_size > 0
