"""Global pytest fixtures to isolate tests from user configuration."""

from pathlib import Path
import pytest
from yt_music_downloader.config import AppConfig


@pytest.fixture(autouse=True)
def isolate_user_config(tmp_path_factory, monkeypatch):
    """Ensure any config.save() or config_file_path() call uses an isolated temp directory."""
    temp_dir = tmp_path_factory.mktemp("test_config")
    fake_config_file = temp_dir / "config.json"
    monkeypatch.setattr(AppConfig, "config_file_path", classmethod(lambda cls: fake_config_file))
