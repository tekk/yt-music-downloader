"""Authentication and cookie management modal screen."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RichLog, Select

from ...browser_auth import (
    BrowserLoginSession,
    check_cookie_file,
    detect_system_chromium,
    extract_from_installed_browser,
)
from ...config import AppConfig


class AuthModal(ModalScreen[Optional[AppConfig]]):
    """Modal dialog for logging into YouTube Music and grabbing cookies."""

    DEFAULT_CSS = """
    AuthModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #auth-dialog {
        width: 80;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #auth-status-box {
        margin: 1 0;
        padding: 0 1;
        height: 3;
        background: $surface-lighten-1;
        layout: horizontal;
        align: left middle;
    }
    #auth-log {
        height: 7;
        margin: 1 0;
        border: solid $surface-lighten-1;
        background: $surface-darken-1;
    }
    .auth-section {
        margin-top: 1;
        padding-top: 1;
        border-top: solid $surface-lighten-1;
    }
    """

    def __init__(self, config: AppConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self._login_session: Optional[BrowserLoginSession] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="auth-dialog"):
            yield Label("🔐 YouTube Music Authentication", id="modal-title", classes="modal-title")

            # Status Banner
            with Horizontal(id="auth-status-box"):
                yield Label("Current Status: ", classes="option-label")
                yield Label("", id="status-display")

            with ScrollableContainer():
                # Method 1: Browser Login
                yield Label("Method 1: Interactive Browser Login (Recommended)", classes="modal-section-title")
                yield Label(
                    "Launches browser with an isolated profile. Sign in with your Google account, and cookies will be grabbed automatically.",
                    classes="modal-desc",
                )
                with Horizontal():
                    yield Button("🚀 Open Browser & Login", id="btn-browser-login", variant="primary")
                    yield Button("🛑 Stop Login", id="btn-stop-login", variant="error", disabled=True)

                # Activity Log
                yield RichLog(id="auth-log", highlight=True, markup=True)

                # Method 2: Direct Browser Extraction
                yield Label("Method 2: 1-Click Sync from Installed Browser", classes="modal-section-title")
                yield Label(
                    "Directly imports active cookies from your default installed browser.",
                    classes="modal-desc",
                )
                with Horizontal():
                    browser_options = [
                        ("Google Chrome", "chrome"),
                        ("Mozilla Firefox", "firefox"),
                        ("Microsoft Edge", "edge"),
                        ("Brave Browser", "brave"),
                        ("Opera", "opera"),
                        ("Chromium", "chromium"),
                    ]
                    yield Select(browser_options, value="chrome", id="select-browser")
                    yield Button("📥 Sync from Browser", id="btn-sync-browser")

                # Method 3: File Import
                yield Label("Method 3: Import Existing cookies.txt File", classes="modal-section-title")
                with Horizontal():
                    yield Input(placeholder="/path/to/cookies.txt", id="input-cookie-path")
                    yield Button("📂 Load File", id="btn-load-file")

            # Bottom Actions
            with Horizontal(classes="modal-buttons"):
                yield Button("🗑 Clear Cookies", id="btn-clear-cookies", variant="warning")
                yield Button("Done / Close", id="btn-close", variant="default")

    def on_mount(self) -> None:
        self.refresh_status()

    def refresh_status(self) -> None:
        status = check_cookie_file(self.config.cookies_path)
        status_label = self.query_one("#status-display", Label)
        if status.is_authenticated:
            cookies_str = ", ".join(status.auth_cookies[:3])
            status_label.update(
                Text.from_markup(f"[bold green]✓ Authenticated[/bold green] ({status.count} cookies, tokens: {cookies_str})")
            )
        elif status.exists:
            status_label.update(
                Text.from_markup(f"[yellow]⚠ Cookies file present ({status.count} cookies, unauthenticated)[/yellow]")
            )
        else:
            status_label.update(
                Text.from_markup("[dim red]✗ Not Logged In (Guest Mode)[/dim red]")
            )

    def log_message(self, msg: str) -> None:
        log = self.query_one("#auth-log", RichLog)
        log.write(msg)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn-browser-login":
            self.start_browser_login()
        elif btn_id == "btn-stop-login":
            self.stop_browser_login()
        elif btn_id == "btn-sync-browser":
            self.sync_from_browser()
        elif btn_id == "btn-load-file":
            self.load_cookie_file()
        elif btn_id == "btn-clear-cookies":
            self.clear_cookies()
        elif btn_id == "btn-close":
            if self._login_session:
                self._login_session.stop()
            self.dismiss(self.config)

    @work(exclusive=True)
    async def start_browser_login(self) -> None:
        """Background worker running the browser login session."""
        self.query_one("#btn-browser-login", Button).disabled = True
        self.query_one("#btn-stop-login", Button).disabled = False

        self.log_message("[bold cyan]Initializing browser session...[/bold cyan]")
        session = BrowserLoginSession(
            target_cookie_path=self.config.cookies_path,
            on_status=self.log_message,
        )
        self._login_session = session

        launched = session.launch_browser()
        if not launched:
            self.query_one("#btn-browser-login", Button).disabled = False
            self.query_one("#btn-stop-login", Button).disabled = True
            return

        status = await session.wait_for_login(timeout=300)
        if status and status.is_authenticated:
            self.log_message("[bold green]✓ Authentication successful! Cookies stored.[/bold green]")
            self.config.save()
            self.refresh_status()
        else:
            self.log_message("[yellow]Browser session finished or cancelled.[/yellow]")

        self.query_one("#btn-browser-login", Button).disabled = False
        self.query_one("#btn-stop-login", Button).disabled = True

    def stop_browser_login(self) -> None:
        if self._login_session:
            self._login_session.stop()
            self.log_message("[red]Stopping browser session...[/red]")
        self.query_one("#btn-browser-login", Button).disabled = False
        self.query_one("#btn-stop-login", Button).disabled = True

    @work(exclusive=True)
    async def sync_from_browser(self) -> None:
        """Sync cookies directly from an installed browser."""
        select = self.query_one("#select-browser", Select)
        browser = select.value
        if not browser:
            return

        self.log_message(f"Attempting to extract cookies from [bold]{browser}[/bold]...")
        try:
            loop = asyncio.get_running_loop()
            status = await loop.run_in_executor(
                None,
                extract_from_installed_browser,
                browser,
                self.config.cookies_path,
            )
            if status.is_authenticated:
                self.log_message(
                    f"[bold green]✓ Successfully synced {status.count} cookies from {browser}![/bold green]"
                )
            elif status.exists:
                self.log_message(
                    f"[yellow]Extracted {status.count} cookies from {browser}, but no YouTube login was found.[/yellow]"
                )
            else:
                self.log_message(f"[red]No cookies found in {browser}.[/red]")
            self.config.save()
            self.refresh_status()
        except Exception as e:
            self.log_message(f"[bold red]Extraction failed:[/bold red] {e}")

    def load_cookie_file(self) -> None:
        """Import custom cookies.txt file."""
        input_widget = self.query_one("#input-cookie-path", Input)
        path_str = input_widget.value.strip()
        if not path_str:
            self.log_message("[red]Please specify a valid file path.[/red]")
            return

        p = Path(path_str).expanduser().resolve()
        if not p.is_file():
            self.log_message(f"[red]File does not exist: {p}[/red]")
            return

        status = check_cookie_file(p)
        if not status.exists or status.count == 0:
            self.log_message(f"[red]File contains no valid cookies: {p}[/red]")
            return

        self.config.cookies_path = str(p)
        self.config.save()
        self.refresh_status()
        self.log_message(f"[bold green]✓ Loaded {status.count} cookies from {p.name}![/bold green]")

    def clear_cookies(self) -> None:
        """Delete current cookies file."""
        p = Path(self.config.cookies_path)
        if p.is_file():
            try:
                p.unlink()
                self.log_message(f"[yellow]Deleted {p.name}.[/yellow]")
            except Exception as e:
                self.log_message(f"[red]Error deleting {p.name}: {e}[/red]")
        self.refresh_status()
