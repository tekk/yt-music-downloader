"""Settings modal screen for configuring application preferences."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Switch

from ...config import AppConfig, get_default_music_dir


class SettingsModal(ModalScreen[Optional[AppConfig]]):
    """Modal dialog for editing app settings."""

    BINDINGS = [
        Binding("escape", "cancel_modal", "Cancel / Close", priority=True),
    ]

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #settings-dialog {
        width: 82;
        height: auto;
        max-height: 95%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        overflow-y: auto;
    }
    .modal-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        border-bottom: solid $surface-lighten-1;
        padding-bottom: 1;
    }
    .modal-section-title {
        text-style: bold;
        color: $accent;
        margin-top: 0;
        margin-bottom: 0;
    }
    .settings-row {
        height: 3;
        margin-bottom: 1;
        layout: horizontal;
        align: left middle;
    }
    .settings-label {
        width: 28;
        text-style: bold;
        color: $text;
    }
    .settings-input {
        width: 1fr;
        margin-right: 1;
    }
    #btn-reset-dir {
        min-width: 12;
    }
    .switch-row {
        height: 3;
        margin-bottom: 1;
        layout: horizontal;
        align: left middle;
    }
    .switch-row Switch {
        height: 3;
        min-width: 10;
        margin-right: 1;
    }
    .switch-row Switch:focus {
        border: thick white;
    }
    .switch-status-label {
        width: 18;
        text-style: bold;
    }
    .modal-buttons {
        height: 4;
        layout: horizontal;
        align: right middle;
        margin-top: 1;
    }
    .modal-buttons Button {
        min-width: 16;
        margin-left: 1;
    }
    """

    def __init__(self, config: AppConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config

    def action_cancel_modal(self) -> None:
        """Cancel and close modal on Esc keypress."""
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Label("⚙ Application Settings", id="modal-title", classes="modal-title")

            # Download Folder
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
                    art_txt = "[bold green]ON (Enabled)[/bold green]" if self.config.embed_artwork else "[dim]OFF (Disabled)[/dim]"
                    yield Label(Text.from_markup(art_txt), id="label-switch-artwork", classes="switch-status-label")

                with Horizontal(classes="switch-row"):
                    yield Label("Embed ID3 / Metadata Tags:", classes="settings-label")
                    yield Switch(value=self.config.embed_metadata, id="switch-metadata")
                    meta_txt = "[bold green]ON (Enabled)[/bold green]" if self.config.embed_metadata else "[dim]OFF (Disabled)[/dim]"
                    yield Label(Text.from_markup(meta_txt), id="label-switch-metadata", classes="switch-status-label")

                with Horizontal(classes="switch-row"):
                    yield Label("Create Folder for Playlists:", classes="settings-label")
                    yield Switch(value=self.config.auto_create_playlist_folder, id="switch-playlist-folder")
                    fold_txt = "[bold green]ON (Enabled)[/bold green]" if self.config.auto_create_playlist_folder else "[dim]OFF (Disabled)[/dim]"
                    yield Label(Text.from_markup(fold_txt), id="label-switch-playlist-folder", classes="switch-status-label")

            # Bottom Buttons
            with Horizontal(classes="modal-buttons"):
                yield Button("Save & Apply", id="btn-save", variant="primary")
                yield Button("Cancel", id="btn-cancel", variant="default")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        switch_id = event.switch.id
        if switch_id:
            lbl_id = f"#label-{switch_id}"
            txt = "[bold green]ON (Enabled)[/bold green]" if event.value else "[dim]OFF (Disabled)[/dim]"
            try:
                self.query_one(lbl_id, Label).update(Text.from_markup(txt))
            except Exception:
                pass

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
