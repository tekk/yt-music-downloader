"""Settings modal screen for configuring application preferences."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Switch

from ...config import AppConfig, get_default_music_dir


class SettingsModal(ModalScreen[Optional[AppConfig]]):
    """Modal dialog for editing app settings."""

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #settings-dialog {
        width: 76;
        height: auto;
        max-height: 85%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    .settings-row {
        height: 3;
        margin-bottom: 1;
        layout: horizontal;
        align: left middle;
    }
    .settings-label {
        width: 26;
        text-style: bold;
        color: $text;
    }
    .settings-input {
        width: 1fr;
    }
    .switch-row {
        height: 2;
        margin-bottom: 1;
        layout: horizontal;
        align: left middle;
    }
    """

    def __init__(self, config: AppConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Label("⚙ Application Settings", id="modal-title", classes="modal-title")

            with ScrollableContainer():
                # Download Folder
                with Vertical():
                    yield Label("Download Directory:", classes="modal-section-title")
                    with Horizontal(classes="settings-row"):
                        yield Input(value=self.config.download_dir, id="input-download-dir", classes="settings-input")
                        yield Button("Reset", id="btn-reset-dir")

                # Default Audio Format
                with Horizontal(classes="settings-row"):
                    yield Label("Default Audio Format:", classes="settings-label")
                    formats = [
                        ("MP3 (Universal compatibility)", "mp3"),
                        ("M4A / AAC (Apple / Modern)", "m4a"),
                        ("Original Stream (No Re-encoding)", "original"),
                        ("FLAC (Lossless Container)", "flac"),
                        ("OPUS (High Efficiency)", "opus"),
                    ]
                    yield Select(formats, value=self.config.audio_format, id="select-format")

                # MP3 Bitrate
                with Horizontal(classes="settings-row"):
                    yield Label("MP3 Quality / Bitrate:", classes="settings-label")
                    qualities = [
                        ("320 kbps (Highest CBR)", "320"),
                        ("256 kbps (High CBR)", "256"),
                        ("192 kbps (Standard CBR)", "192"),
                        ("VBR 0 (Best Variable)", "0"),
                    ]
                    yield Select(qualities, value=self.config.mp3_quality, id="select-quality")

                # Theme Selection
                with Horizontal(classes="settings-row"):
                    yield Label("Terminal Theme:", classes="settings-label")
                    themes = [
                        ("Textual Dark (Default)", "textual-dark"),
                        ("Textual Light", "textual-light"),
                        ("Nord", "nord"),
                        ("Solarized Light", "solarized-light"),
                        ("Solarized Dark", "solarized-dark"),
                        ("Dracula", "dracula"),
                        ("Tokyo Night", "tokyo-night"),
                        ("Gruvbox", "gruvbox"),
                    ]
                    yield Select(themes, value=self.config.theme, id="select-theme")

                # Toggles
                with Horizontal(classes="switch-row"):
                    yield Label("Embed Cover Artwork:", classes="settings-label")
                    yield Switch(value=self.config.embed_artwork, id="switch-artwork")

                with Horizontal(classes="switch-row"):
                    yield Label("Embed ID3 / Metadata Tags:", classes="settings-label")
                    yield Switch(value=self.config.embed_metadata, id="switch-metadata")

                with Horizontal(classes="switch-row"):
                    yield Label("Create Folder for Playlists:", classes="settings-label")
                    yield Switch(value=self.config.auto_create_playlist_folder, id="switch-playlist-folder")

            # Bottom Buttons
            with Horizontal(classes="modal-buttons"):
                yield Button("Save & Apply", id="btn-save", variant="primary")
                yield Button("Cancel", id="btn-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-reset-dir":
            self.query_one("#input-download-dir", Input).value = str(get_default_music_dir())
        elif event.button.id == "btn-save":
            self.save_settings()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def save_settings(self) -> None:
        new_dir = self.query_one("#input-download-dir", Input).value.strip()
        if new_dir:
            self.config.download_dir = str(Path(new_dir).expanduser())

        self.config.audio_format = self.query_one("#select-format", Select).value or "mp3"
        self.config.mp3_quality = self.query_one("#select-quality", Select).value or "320"
        self.config.theme = self.query_one("#select-theme", Select).value or "textual-dark"
        self.config.embed_artwork = self.query_one("#switch-artwork", Switch).value
        self.config.embed_metadata = self.query_one("#switch-metadata", Switch).value
        self.config.auto_create_playlist_folder = self.query_one("#switch-playlist-folder", Switch).value

        self.config.save()
        self.dismiss(self.config)
