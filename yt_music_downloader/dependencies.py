"""System dependency detection and validation for YouTube Music Downloader."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import AppConfig


@dataclass
class DependencyStatus:
    """Status details for an external binary or component."""

    name: str
    required: bool
    available: bool
    path: Optional[str] = None
    version: Optional[str] = None
    description: str = ""
    install_guide: str = ""


@dataclass
class DependencyReport:
    """Consolidated report of all system dependencies."""

    items: List[DependencyStatus] = field(default_factory=list)

    @property
    def all_required_met(self) -> bool:
        """True if all required dependencies are available."""
        return all(item.available for item in self.items if item.required)

    @property
    def missing_required(self) -> List[DependencyStatus]:
        """List of required dependencies that are missing."""
        return [item for item in self.items if item.required and not item.available]

    @property
    def missing_optional(self) -> List[DependencyStatus]:
        """List of optional dependencies that are missing."""
        return [item for item in self.items if not item.required and not item.available]


def get_os_info() -> str:
    """Return friendly OS description or Linux distribution identifier."""
    system = platform.system()
    if system == "Linux":
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            return line.split("=", 1)[1].strip('"\n')
                        if line.startswith("ID="):
                            return line.split("=", 1)[1].strip('"\n').lower()
        except Exception:
            pass
        return "Linux"
    if system == "Darwin":
        return "macOS"
    if system == "Windows":
        return "Windows"
    return system


def get_ffmpeg_install_guide() -> str:
    """Generate OS-specific installation instructions for FFmpeg."""
    system = platform.system()

    if system == "Darwin":
        return "brew install ffmpeg"

    if system == "Windows":
        return "winget install Gyan.FFmpeg\n# Or via Chocolatey:\nchoco install ffmpeg"

    if system == "Linux":
        distro = ""
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    if "arch" in content or "manjaro" in content:
                        distro = "arch"
                    elif "fedora" in content or "rhel" in content or "centos" in content:
                        distro = "fedora"
                    elif "debian" in content or "ubuntu" in content or "mint" in content or "pop" in content:
                        distro = "debian"
                    elif "suse" in content:
                        distro = "suse"
                    elif "alpine" in content:
                        distro = "alpine"
        except Exception:
            pass

        if distro == "arch":
            return "sudo pacman -S ffmpeg"
        elif distro == "debian":
            return "sudo apt update && sudo apt install ffmpeg"
        elif distro == "fedora":
            return "sudo dnf install ffmpeg"
        elif distro == "suse":
            return "sudo zypper install ffmpeg"
        elif distro == "alpine":
            return "apk add ffmpeg"
        else:
            return (
                "sudo apt install ffmpeg    # Debian / Ubuntu / Mint\n"
                "sudo pacman -S ffmpeg     # Arch Linux / Manjaro\n"
                "sudo dnf install ffmpeg   # Fedora / RHEL"
            )

    return "Visit https://ffmpeg.org/download.html for installation instructions."


def get_binary_version(binary_path: str) -> Optional[str]:
    """Retrieve version string from an executable by calling -version."""
    try:
        res = subprocess.run(
            [binary_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=2,
        )
        lines = res.stdout.strip().splitlines()
        if lines:
            first_line = lines[0].strip()
            # Trim trailing copyright notice for clean display
            if " Copyright" in first_line:
                first_line = first_line.split(" Copyright")[0].strip()
            return first_line
    except Exception:
        pass
    return None


def check_ffmpeg() -> DependencyStatus:
    """Inspect system PATH for FFmpeg."""
    path = shutil.which("ffmpeg")
    available = path is not None
    version = get_binary_version(path) if path else None

    return DependencyStatus(
        name="FFmpeg",
        required=True,
        available=available,
        path=path,
        version=version,
        description="Audio conversion (MP3, M4A, FLAC, Opus) & metadata/cover art embedding",
        install_guide=get_ffmpeg_install_guide(),
    )


def check_ffprobe() -> DependencyStatus:
    """Inspect system PATH for FFprobe."""
    path = shutil.which("ffprobe")
    available = path is not None
    version = get_binary_version(path) if path else None

    return DependencyStatus(
        name="FFprobe",
        required=False,
        available=available,
        path=path,
        version=version,
        description="Media stream & codec inspector used by yt-dlp",
        install_guide=get_ffmpeg_install_guide(),
    )


def check_browsers() -> List[DependencyStatus]:
    """Inspect available browsers that can be used for YouTube Music cookie extraction."""
    from .browser_auth import detect_system_chromium

    results: List[DependencyStatus] = []

    # 1. Chromium / Chrome / Brave / Edge
    chromium_path = detect_system_chromium()
    results.append(
        DependencyStatus(
            name="Chromium / Chrome Browser",
            required=False,
            available=chromium_path is not None,
            path=chromium_path,
            description="Used for isolated browser login and 1-click cookie capture",
            install_guide="Install Google Chrome, Chromium, Brave, or Microsoft Edge.",
        )
    )

    # 2. Firefox
    firefox_path = shutil.which("firefox")
    results.append(
        DependencyStatus(
            name="Mozilla Firefox",
            required=False,
            available=firefox_path is not None,
            path=firefox_path,
            description="Alternative browser supported for 1-click cookie sync",
            install_guide="Install Mozilla Firefox from your package manager or browser website.",
        )
    )

    return results


def check_all_dependencies() -> DependencyReport:
    """Run full system dependency checks."""
    items: List[DependencyStatus] = [
        check_ffmpeg(),
        check_ffprobe(),
    ]
    items.extend(check_browsers())
    return DependencyReport(items=items)


def verify_ffmpeg_requirement(config: AppConfig) -> tuple[bool, str]:
    """Check if FFmpeg is available when current configuration requires it.

    Returns:
        (True, "") if FFmpeg is available OR if current settings don't need FFmpeg.
        (False, install_instructions) if FFmpeg is missing and needed.
    """
    audio_format = (config.audio_format or "mp3").lower()
    needs_ffmpeg = (
        audio_format in ("mp3", "m4a", "flac", "opus")
        or config.embed_artwork
        or config.embed_metadata
    )

    if not needs_ffmpeg:
        return True, ""

    ffmpeg_stat = check_ffmpeg()
    if ffmpeg_stat.available:
        return True, ""

    reasons = []
    if audio_format in ("mp3", "m4a", "flac", "opus"):
        reasons.append(f"re-encode to {audio_format.upper()}")
    if config.embed_metadata:
        reasons.append("write ID3/MP4 metadata tags")
    if config.embed_artwork:
        reasons.append("embed album artwork")

    msg = (
        f"FFmpeg is required to {', '.join(reasons)}, but was not found in your system PATH.\n\n"
        f"To install FFmpeg on {get_os_info()}:\n  {ffmpeg_stat.install_guide}\n\n"
        f"Alternatively, choose audio format 'original' with metadata and artwork embedding disabled."
    )
    return False, msg


def create_dependency_table(report: DependencyReport) -> Table:
    """Format dependency report into a Rich Table."""
    table = Table(
        title="🛠️ System Dependencies & External Tools",
        title_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Component", style="bold white", width=22)
    table.add_column("Type", width=10)
    table.add_column("Status", width=14)
    table.add_column("Path / Version", style="dim", width=36)
    table.add_column("Description", width=32)

    for item in report.items:
        typ = "[bold red]Required[/bold red]" if item.required else "[dim]Optional[/dim]"
        if item.available:
            status = "[bold green]✓ Installed[/bold green]"
            detail = item.version or item.path or "Found"
        else:
            if item.required:
                status = "[bold red]✗ Missing[/bold red]"
            else:
                status = "[yellow]! Not Found[/yellow]"
            detail = "[italic dim]Not detected[/italic dim]"

        table.add_row(item.name, typ, status, detail, item.description)

    return table


def print_dependency_report(
    report: Optional[DependencyReport] = None,
    console: Optional[Console] = None,
) -> int:
    """Print formatted dependency report to console.

    Returns:
        0 if all required dependencies are met, 1 if any required dependencies are missing.
    """
    if console is None:
        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding="utf-8")
                sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass
        console = Console(legacy_windows=False)
    report = report or check_all_dependencies()

    table = create_dependency_table(report)
    console.print()
    console.print(table)
    console.print()

    if not report.all_required_met:
        missing_req = report.missing_required
        msg_lines = ["[bold red]Missing Required Dependencies:[/bold red]"]
        for item in missing_req:
            msg_lines.append(f"\n• [bold]{item.name}[/bold]: {item.description}")
            if item.install_guide:
                msg_lines.append(f"  [cyan]Install guide ({get_os_info()}):[/cyan]")
                for line in item.install_guide.splitlines():
                    msg_lines.append(f"    [yellow]{line}[/yellow]")

        console.print(
            Panel(
                "\n".join(msg_lines),
                title="[bold red]Action Required[/bold red]",
                border_style="red",
            )
        )
        return 1

    console.print("[bold green]✓ All required dependencies are satisfied![/bold green]\n")
    return 0
