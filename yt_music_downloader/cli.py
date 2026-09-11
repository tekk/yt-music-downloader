"""Command-line interface entry point for YT Music Downloader."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import AppConfig
from .ui.app import YTMusicDownloaderApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="yt-music-dl",
        description="Cross-platform TUI application for downloading YouTube Music with highest quality audio.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="",
        help="Optional initial YouTube Music playlist, album, or song URL.",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["original", "mp3", "m4a", "flac", "opus"],
        help="Audio format (default: mp3)",
    )
    parser.add_argument(
        "-q", "--quality",
        choices=["320", "256", "192", "0"],
        help="MP3 bitrate / quality (default: 320)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        help="Custom download directory",
    )
    parser.add_argument(
        "-c", "--cookies",
        help="Path to custom cookies.txt file",
    )
    parser.add_argument(
        "-t", "--theme",
        help="Terminal theme (e.g. textual-dark, textual-light, nord, solarized-light)",
    )
    parser.add_argument(
        "-g", "--gui",
        action="store_true",
        help="Launch modern Desktop GUI client instead of terminal TUI",
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check external system dependencies (FFmpeg, browsers) and exit",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.check_deps:
        from .dependencies import print_dependency_report
        sys.exit(print_dependency_report())

    # Check for critical dependencies
    from .dependencies import check_ffmpeg
    ffmpeg_stat = check_ffmpeg()
    if not ffmpeg_stat.available:
        print(
            f"⚠️  WARNING: FFmpeg was not found in PATH!\n"
            f"   Audio conversion (MP3, M4A, FLAC, Opus) and thumbnail embedding require FFmpeg.\n"
            f"   Install instructions ({ffmpeg_stat.install_guide}):\n   {ffmpeg_stat.install_guide}\n",
            file=sys.stderr,
        )

    config = AppConfig.load()

    if args.format:
        config.audio_format = args.format
    if args.quality:
        config.mp3_quality = args.quality
    if args.output_dir:
        config.download_dir = str(Path(args.output_dir).expanduser().resolve())
    if args.cookies:
        config.cookies_path = str(Path(args.cookies).expanduser().resolve())
    if args.theme:
        config.theme = args.theme

    if args.gui:
        from PyQt6.QtWidgets import QApplication
        from .gui.app import MainWindow
        from .gui.styles import DARK_THEME_QSS, load_application_fonts

        qapp = QApplication(sys.argv)
        load_application_fonts()
        qapp.setStyleSheet(DARK_THEME_QSS)
        win = MainWindow(config=config, initial_url=args.url)
        win.show()
        sys.exit(qapp.exec())

    app = YTMusicDownloaderApp(config=config, initial_url=args.url)
    app.run()


if __name__ == "__main__":
    main()
