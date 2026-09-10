"""Modern 4-tab Authentication and Cookie Manager modal dialog for PyQt6."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...browser_auth import (
    BrowserLoginSession,
    check_cookie_file,
    detect_system_chromium,
    extract_from_installed_browser,
)
from ...config import AppConfig


class BrowserLoginWorker(QThread):
    """Background worker for browser login and CDP cookie detection."""

    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, cookies_path: str):
        super().__init__()
        self.cookies_path = cookies_path
        self.session: Optional[BrowserLoginSession] = None

    def run(self):
        self.session = BrowserLoginSession(
            target_cookie_path=self.cookies_path,
            on_status=lambda msg: self.status_signal.emit(msg),
        )
        if not self.session.launch_browser():
            self.finished_signal.emit(False)
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status = loop.run_until_complete(self.session.wait_for_login(timeout=300))
            self.finished_signal.emit(bool(status and status.is_authenticated))
        except Exception as e:
            self.status_signal.emit(f"Error: {e}")
            self.finished_signal.emit(False)
        finally:
            loop.close()

    def stop(self):
        if self.session:
            self.session.stop()


class AuthDialog(QDialog):
    """Modern modal dialog managing YouTube Music authentication and cookies."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("YouTube Music Authentication & Cookies")
        self.setMinimumSize(700, 520)
        self.login_worker: Optional[BrowserLoginWorker] = None

        self._build_ui()
        self.refresh_status()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header Title
        lbl_title = QLabel("🔐 YouTube Music Authentication")
        lbl_title.setObjectName("app-title")
        lbl_title.setFont(QFont("Montserrat", 16, QFont.Weight.Bold))
        main_layout.addWidget(lbl_title)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Browser Login
        self.tabs.addTab(self._create_tab_browser_login(), "🌐 Browser Login")

        # Tab 2: 1-Click Sync
        self.tabs.addTab(self._create_tab_sync(), "⚡ 1-Click Sync")

        # Tab 3: Import File
        self.tabs.addTab(self._create_tab_import(), "📂 Import File")

        # Tab 4: Cookie Status
        self.tabs.addTab(self._create_tab_status(), "ℹ Cookie Status")

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_close = QPushButton("Done / Close")
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)
        main_layout.addLayout(bottom_layout)

    def _create_tab_browser_login(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl_desc = QLabel(
            "Launches an isolated browser window directed to YouTube Music.\n"
            "Log in to your Google Account. Cookies will be captured automatically!"
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        layout.addWidget(lbl_desc)

        btn_row = QHBoxLayout()
        self.btn_start_login = QPushButton("🚀 Open Browser & Log In")
        self.btn_start_login.setObjectName("btn-inspect")
        self.btn_start_login.clicked.connect(self._start_browser_login)
        btn_row.addWidget(self.btn_start_login)

        self.btn_stop_login = QPushButton("⏹ Stop")
        self.btn_stop_login.setEnabled(False)
        self.btn_stop_login.clicked.connect(self._stop_browser_login)
        btn_row.addWidget(self.btn_stop_login)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.log_browser = QPlainTextEdit()
        self.log_browser.setObjectName("log-console")
        self.log_browser.setReadOnly(True)
        layout.addWidget(self.log_browser)

        return widget

    def _create_tab_sync(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        lbl_desc = QLabel(
            "If you are already logged into YouTube Music in your standard desktop browser,\n"
            "you can extract your cookies with one click without opening a new login window."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        layout.addWidget(lbl_desc)

        sync_row = QHBoxLayout()
        lbl_choose = QLabel("Select Browser:")
        lbl_choose.setStyleSheet("font-weight: bold;")
        sync_row.addWidget(lbl_choose)

        self.cb_browser = QComboBox()
        self.cb_browser.addItems(["chrome", "firefox", "edge", "brave", "opera"])
        sync_row.addWidget(self.cb_browser)

        self.btn_sync = QPushButton("📥 Sync Cookies")
        self.btn_sync.setObjectName("btn-my-playlists")
        self.btn_sync.clicked.connect(self._sync_browser_cookies)
        sync_row.addWidget(self.btn_sync)
        sync_row.addStretch()
        layout.addLayout(sync_row)

        self.lbl_sync_feedback = QLabel("")
        self.lbl_sync_feedback.setFont(QFont("Roboto", 13))
        layout.addWidget(self.lbl_sync_feedback)
        layout.addStretch()
        return widget

    def _create_tab_import(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        lbl_desc = QLabel(
            "Load a custom Netscape-format 'cookies.txt' file exported via browser extension."
        )
        lbl_desc.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        layout.addWidget(lbl_desc)

        row = QHBoxLayout()
        self.btn_browse_cookie = QPushButton("📁 Browse cookies.txt...")
        self.btn_browse_cookie.clicked.connect(self._browse_cookie_file)
        row.addWidget(self.btn_browse_cookie)
        row.addStretch()
        layout.addLayout(row)

        self.lbl_import_feedback = QLabel("")
        self.lbl_import_feedback.setFont(QFont("Roboto", 13))
        layout.addWidget(self.lbl_import_feedback)
        layout.addStretch()
        return widget

    def _create_tab_status(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.lbl_status_summary = QLabel("Checking cookie file...")
        self.lbl_status_summary.setFont(QFont("Roboto", 14, QFont.Weight.Bold))
        layout.addWidget(self.lbl_status_summary)

        self.lbl_status_details = QLabel("")
        self.lbl_status_details.setStyleSheet("color: #AAAAAA; font-family: 'JetBrains Mono';")
        layout.addWidget(self.lbl_status_details)

        btn_row = QHBoxLayout()
        self.btn_clear_cookies = QPushButton("🗑 Clear Stored Cookies")
        self.btn_clear_cookies.setObjectName("btn-cancel")
        self.btn_clear_cookies.clicked.connect(self._clear_cookies)
        btn_row.addWidget(self.btn_clear_cookies)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        return widget

    # Logic
    def refresh_status(self):
        status = check_cookie_file(self.config.cookies_path)
        if status.is_authenticated:
            self.lbl_status_summary.setText("🔒 Status: Authenticated (Logged In)")
            self.lbl_status_summary.setStyleSheet("color: #00E676; font-weight: bold;")
            details = (
                f"File: {self.config.cookies_path}\n"
                f"Total Cookies: {status.count}\n"
                f"Auth Tokens: {', '.join(status.auth_cookies)}"
            )
            self.lbl_status_details.setText(details)
        elif status.exists:
            self.lbl_status_summary.setText("⚠ Status: Guest Cookies (No Active Login)")
            self.lbl_status_summary.setStyleSheet("color: #FFB300; font-weight: bold;")
            self.lbl_status_details.setText(f"File: {self.config.cookies_path}\nTotal Cookies: {status.count}")
        else:
            self.lbl_status_summary.setText("🔓 Status: Not Authenticated (No Cookies)")
            self.lbl_status_summary.setStyleSheet("color: #FF5252; font-weight: bold;")
            self.lbl_status_details.setText(f"No cookies file found at:\n{self.config.cookies_path}")

    def _start_browser_login(self):
        self.btn_start_login.setEnabled(False)
        self.btn_stop_login.setEnabled(True)
        self.log_browser.appendPlainText("Starting browser login...")

        self.login_worker = BrowserLoginWorker(self.config.cookies_path)
        self.login_worker.status_signal.connect(self.log_browser.appendPlainText)
        self.login_worker.finished_signal.connect(self._on_login_finished)
        self.login_worker.start()

    def _stop_browser_login(self):
        if self.login_worker:
            self.login_worker.stop()
        self.btn_start_login.setEnabled(True)
        self.btn_stop_login.setEnabled(False)
        self.log_browser.appendPlainText("Stopped browser session.")

    def _on_login_finished(self, success: bool):
        self.btn_start_login.setEnabled(True)
        self.btn_stop_login.setEnabled(False)
        if success:
            self.log_browser.appendPlainText("✓ Login successful! Stored session cookies.")
            self.refresh_status()
        else:
            self.log_browser.appendPlainText("Browser session closed.")

    def _sync_browser_cookies(self):
        browser = self.cb_browser.currentText()
        self.lbl_sync_feedback.setText(f"Extracting cookies from {browser}...")
        self.lbl_sync_feedback.setStyleSheet("color: #00E5FF;")
        try:
            status = extract_from_installed_browser(browser, self.config.cookies_path)
            if status.is_authenticated:
                self.lbl_sync_feedback.setText(f"✓ Successfully synced {status.count} cookies from {browser}!")
                self.lbl_sync_feedback.setStyleSheet("color: #00E676; font-weight: bold;")
                self.refresh_status()
            else:
                self.lbl_sync_feedback.setText(f"Found cookies from {browser}, but no active login tokens.")
                self.lbl_sync_feedback.setStyleSheet("color: #FFB300;")
        except Exception as e:
            self.lbl_sync_feedback.setText(f"Sync error: {e}")
            self.lbl_sync_feedback.setStyleSheet("color: #FF5252;")

    def _browse_cookie_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Netscape cookies.txt",
            str(Path.home()),
            "Text Files (*.txt);;All Files (*)",
        )
        if path:
            self.config.cookies_path = path
            self.config.save()
            self.lbl_import_feedback.setText(f"✓ Loaded cookies from {Path(path).name}!")
            self.lbl_import_feedback.setStyleSheet("color: #00E676; font-weight: bold;")
            self.refresh_status()

    def _clear_cookies(self):
        p = Path(self.config.cookies_path)
        if p.exists():
            p.unlink()
        self.refresh_status()

    def reject(self):
        self._stop_browser_login()
        super().reject()

    def closeEvent(self, event):
        self._stop_browser_login()
        if self.login_worker and self.login_worker.isRunning():
            self.login_worker.quit()
            self.login_worker.wait(1000)
        super().closeEvent(event)

    def done(self, r):
        self._stop_browser_login()
        if self.login_worker and self.login_worker.isRunning():
            self.login_worker.quit()
            self.login_worker.wait(1000)
        super().done(r)
