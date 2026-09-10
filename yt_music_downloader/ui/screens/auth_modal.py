"""Authentication and cookie management modal screen with tabbed interface."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    RichLog,
    Select,
    TabbedContent,
    TabPane,
)

from ...browser_auth import (
    BrowserLoginSession,
    check_cookie_file,
    detect_system_chromium,
    extract_from_installed_browser,
)
from ...config import AppConfig


class ConfirmButton(Button):
    """Button that visually transforms with high-contrast indicators when focused."""

    def __init__(self, label: str = "✓ Accept & Continue", *args, **kwargs):
        super().__init__(label, *args, **kwargs)
        self._raw_label = label

    def set_clean_label(self, text: str) -> None:
        self._raw_label = text
        if self.has_focus:
            self.label = f"▶ {text} ◀"
        else:
            self.label = text

    def on_focus(self) -> None:
        clean = str(self._raw_label or self.label).strip("▶◀ ")
        self.label = f"▶ {clean} ◀"

    def on_blur(self) -> None:
        clean = str(self._raw_label or self.label).strip("▶◀ ")
        self.label = clean


class AuthModal(ModalScreen[Optional[AppConfig]]):
    """Modal dialog with tabbed options for logging in and managing cookies."""

    DEFAULT_CSS = """
    AuthModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #auth-dialog {
        width: 86;
        height: 32;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        layout: vertical;
    }
    #auth-header {
        height: 2;
        layout: horizontal;
        align: left middle;
        border-bottom: solid $surface-lighten-1;
        margin-bottom: 1;
    }
    #auth-title {
        text-style: bold;
        color: $primary;
        width: 1fr;
    }
    #auth-current-badge {
        height: 1;
        padding: 0 1;
        text-style: bold;
    }
    #auth-tabs {
        height: 1fr;
    }
    TabPane {
        padding: 1 1 0 1;
        layout: vertical;
    }
    .tab-instruction {
        color: $text;
        margin-bottom: 1;
    }
    .tab-help {
        color: $text-muted;
        margin-bottom: 1;
    }
    .auth-btn-row {
        height: 3;
        layout: horizontal;
        align: left middle;
        margin-bottom: 1;
    }
    .auth-btn-row Button {
        margin-right: 1;
    }
    #auth-log {
        height: 9;
        margin-top: 1;
        border: solid $surface-lighten-1;
        background: $surface-darken-1;
    }
    .sync-row {
        height: 3;
        layout: horizontal;
        align: left middle;
        margin-bottom: 1;
    }
    #select-browser {
        width: 30;
        margin-right: 1;
    }
    #feedback-sync, #feedback-import {
        height: 2;
        margin-top: 1;
        text-style: bold;
    }
    .info-row {
        height: 2;
        layout: horizontal;
        align: left middle;
        margin-bottom: 1;
    }
    .info-label {
        width: 22;
        text-style: bold;
        color: $text-muted;
    }
    .info-value {
        width: 1fr;
        color: $text;
    }
    #auth-footer {
        height: 4;
        dock: bottom;
        layout: horizontal;
        align: left middle;
        border-top: solid $surface-lighten-1;
        padding: 0 1;
    }
    #footer-auth-status {
        width: 1fr;
        height: 1;
        text-style: bold;
    }
    #btn-close {
        height: 3;
        min-width: 26;
        text-style: bold;
        background: $surface;
        color: $success;
        border: tall $success;
    }
    #btn-close:hover {
        background: $surface-lighten-1;
        border: thick $success;
    }
    #btn-close:focus {
        background: $success;
        color: #000000;
        border: thick white;
        text-style: bold;
    }
    #btn-close.auth-btn-default {
        background: $surface;
        color: $text;
        border: tall $surface-lighten-2;
    }
    #btn-close.auth-btn-default:focus {
        background: $primary;
        color: #000000;
        border: thick white;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close", priority=True),
    ]

    def __init__(self, config: AppConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self._login_session: Optional[BrowserLoginSession] = None

    def action_dismiss_modal(self) -> None:
        """Close modal on Esc keypress."""
        if self._login_session:
            self._login_session.stop()
        self.dismiss(self.config)

    def compose(self) -> ComposeResult:
        with Vertical(id="auth-dialog"):
            # Header
            with Horizontal(id="auth-header"):
                yield Label("🔐 YouTube Music Authentication", id="auth-title")
                yield Label("", id="auth-current-badge")

            # Tabbed content for clean separation
            with TabbedContent(id="auth-tabs"):
                # TAB 1: Browser Login (Automated)
                with TabPane("🚀 Browser Login", id="tab-browser"):
                    yield Label(
                        "Open YouTube Music in an isolated browser to sign in. Cookies will be grabbed automatically.",
                        classes="tab-instruction",
                    )
                    with Horizontal(classes="auth-btn-row"):
                        yield Button("🚀 Launch Browser & Login", id="btn-browser-login", variant="primary")
                        yield Button("🛑 Stop Login", id="btn-stop-login", variant="error", disabled=True)

                    yield RichLog(id="auth-log", highlight=True, markup=True)

                # TAB 2: 1-Click Sync from Installed Browser
                with TabPane("📥 1-Click Sync", id="tab-sync"):
                    yield Label(
                        "Import active cookies directly from your default installed browser (no new login required):",
                        classes="tab-instruction",
                    )
                    with Horizontal(classes="sync-row"):
                        browser_options = [
                            ("Google Chrome", "chrome"),
                            ("Mozilla Firefox", "firefox"),
                            ("Microsoft Edge", "edge"),
                            ("Brave Browser", "brave"),
                            ("Opera", "opera"),
                            ("Chromium", "chromium"),
                        ]
                        yield Select(browser_options, value="chrome", id="select-browser")
                        yield Button("📥 Sync from Browser", id="btn-sync-browser", variant="primary")

                    yield Label("Click 'Sync from Browser' to extract session cookies.", id="feedback-sync")

                # TAB 3: Import File
                with TabPane("📁 Import File", id="tab-import"):
                    yield Label(
                        "Import an existing Netscape format cookies.txt file from disk:",
                        classes="tab-instruction",
                    )
                    with Horizontal(classes="sync-row"):
                        yield Input(
                            placeholder="Path to cookies.txt (e.g. ~/Downloads/cookies.txt)",
                            id="input-cookie-path",
                        )
                        yield Button("📂 Load File", id="btn-load-file", variant="primary")

                    yield Label("Specify a path and click 'Load File'.", id="feedback-import")

                # TAB 4: Cookie Info & Reset
                with TabPane("ℹ Cookie Status", id="tab-info"):
                    with Horizontal(classes="info-row"):
                        yield Label("Status:", classes="info-label")
                        yield Label("", id="info-status", classes="info-value")

                    with Horizontal(classes="info-row"):
                        yield Label("File Location:", classes="info-label")
                        yield Label(self.config.cookies_path, id="info-path", classes="info-value")

                    with Horizontal(classes="info-row"):
                        yield Label("Total Cookies:", classes="info-label")
                        yield Label("0", id="info-count", classes="info-value")

                    with Horizontal(classes="info-row"):
                        yield Label("Tokens Detected:", classes="info-label")
                        yield Label("None", id="info-tokens", classes="info-value")

                    with Horizontal(classes="auth-btn-row"):
                        yield Button("🗑 Clear / Delete Saved Cookies", id="btn-clear-cookies", variant="error")

            # Footer
            with Horizontal(id="auth-footer"):
                yield Label("", id="footer-auth-status")
                yield ConfirmButton("✓ Accept & Continue", id="btn-close", classes="auth-btn-success")

    def on_mount(self) -> None:
        self.refresh_status()
        self.log_message("[dim]Ready. Click 'Launch Browser & Login' to begin authentication.[/dim]")

    def refresh_status(self) -> None:
        status = check_cookie_file(self.config.cookies_path)

        # Header Badge & Footer status
        badge = self.query_one("#auth-current-badge", Label)
        footer_status = self.query_one("#footer-auth-status", Label)
        close_btn = self.query_one("#btn-close", ConfirmButton)

        if status.is_authenticated:
            badge.update(Text.from_markup(f"[bold green]✓ Authenticated ({status.count} cookies)[/bold green]"))
            footer_status.update(Text.from_markup(f"[bold green]✓ Ready • {status.count} session cookies active[/bold green]"))
            close_btn.set_class(True, "auth-btn-success")
            close_btn.set_class(False, "auth-btn-default")
            close_btn.set_clean_label("✓ Accept & Continue")
        elif status.exists:
            badge.update(Text.from_markup(f"[yellow]⚠ Cookies found ({status.count}, guest)[/yellow]"))
            footer_status.update(Text.from_markup(f"[yellow]⚠ Cookies found ({status.count}), but no active login[/yellow]"))
            close_btn.set_class(False, "auth-btn-success")
            close_btn.set_class(True, "auth-btn-default")
            close_btn.set_clean_label("Close")
        else:
            badge.update(Text.from_markup("[dim red]✗ Not Logged In[/dim red]"))
            footer_status.update(Text.from_markup("[dim]Guest mode (standard bitrate)[/dim]"))
            close_btn.set_class(False, "auth-btn-success")
            close_btn.set_class(True, "auth-btn-default")
            close_btn.set_clean_label("Close")

        # Info Tab Labels
        info_status = self.query_one("#info-status", Label)
        info_count = self.query_one("#info-count", Label)
        info_tokens = self.query_one("#info-tokens", Label)
        info_path = self.query_one("#info-path", Label)

        info_path.update(self.config.cookies_path)
        info_count.update(str(status.count))

        if status.is_authenticated:
            info_status.update(Text.from_markup("[bold green]✓ Authenticated (Premium / Account active)[/bold green]"))
            info_tokens.update(Text.from_markup(f"[cyan]{', '.join(status.auth_cookies)}[/cyan]"))
        elif status.exists:
            info_status.update(Text.from_markup("[yellow]Cookies present without login tokens[/yellow]"))
            info_tokens.update("None")
        else:
            info_status.update(Text.from_markup("[dim red]No cookies saved[/dim red]"))
            info_tokens.update("None")

    def log_message(self, msg: str) -> None:
        try:
            log = self.query_one("#auth-log", RichLog)
            log.write(msg)
        except Exception:
            pass

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
        """Background worker running browser login."""
        self.query_one("#btn-browser-login", Button).disabled = True
        self.query_one("#btn-stop-login", Button).disabled = False

        self.log_message("[bold cyan]▶ Starting browser session...[/bold cyan]")
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
            self.log_message("[yellow]Browser session finished or stopped.[/yellow]")

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
        feedback = self.query_one("#feedback-sync", Label)
        browser = select.value
        if not browser:
            return

        feedback.update(Text.from_markup(f"[cyan]Extracting cookies from [bold]{browser}[/bold]...[/cyan]"))
        try:
            loop = asyncio.get_running_loop()
            status = await loop.run_in_executor(
                None,
                extract_from_installed_browser,
                browser,
                self.config.cookies_path,
            )
            if status.is_authenticated:
                feedback.update(
                    Text.from_markup(
                        f"[bold green]✓ Successfully synced {status.count} cookies from {browser}![/bold green]"
                    )
                )
            elif status.exists:
                feedback.update(
                    Text.from_markup(
                        f"[yellow]Synced {status.count} cookies, but no active YouTube login found in {browser}.[/yellow]"
                    )
                )
            else:
                feedback.update(Text.from_markup(f"[red]No cookies found in {browser}.[/red]"))

            self.config.save()
            self.refresh_status()
        except Exception as e:
            feedback.update(Text.from_markup(f"[bold red]Extraction failed:[/bold red] {e}"))

    def load_cookie_file(self) -> None:
        """Import custom cookies.txt file."""
        input_widget = self.query_one("#input-cookie-path", Input)
        feedback = self.query_one("#feedback-import", Label)
        path_str = input_widget.value.strip()
        if not path_str:
            feedback.update(Text.from_markup("[red]Please specify a file path.[/red]"))
            return

        p = Path(path_str).expanduser().resolve()
        if not p.is_file():
            feedback.update(Text.from_markup(f"[red]File does not exist: {p}[/red]"))
            return

        status = check_cookie_file(p)
        if not status.exists or status.count == 0:
            feedback.update(Text.from_markup(f"[red]File contains no valid cookies: {p.name}[/red]"))
            return

        self.config.cookies_path = str(p)
        self.config.save()
        self.refresh_status()
        feedback.update(Text.from_markup(f"[bold green]✓ Loaded {status.count} cookies from {p.name}![/bold green]"))

    def clear_cookies(self) -> None:
        """Delete current cookies file."""
        p = Path(self.config.cookies_path)
        if p.is_file():
            try:
                p.unlink()
                self.refresh_status()
            except Exception as e:
                pass
        self.refresh_status()
