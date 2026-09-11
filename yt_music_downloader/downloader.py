"""YouTube Music playlist and track download engine using yt-dlp and FFmpeg."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yt_dlp
from yt_dlp.postprocessor import PostProcessor

from .config import AppConfig
from .dependencies import verify_ffmpeg_requirement

logger = logging.getLogger(__name__)

# Template for naming songs: {Artist name(s)} - {Track title}.%(ext)s
SONG_FILENAME_TEMPLATE = "%(clean_artist,artists,artist,creator,uploader,channel)l - %(clean_title,track,title)s.%(ext)s"


def sanitize_filename_component(name: str) -> str:
    """Sanitize a filename component, removing illegal filesystem characters."""
    clean = name.replace("/", "-").replace("\\", "-")
    clean = re.sub(r'[<>:"|?*\x00-\x1f]', "", clean)
    clean = re.sub(r"\s+", " ", clean)
    clean = re.sub(r"-+", "-", clean)
    clean = clean.strip(" .-")
    return clean or "Unknown"


def extract_artist_and_title(
    info: Dict[str, Any],
    fallback_artist: str = "Unknown Artist",
    fallback_title: str = "Unknown Title",
) -> Tuple[str, str]:
    """Extract and format '{Artist name(s)}' and '{Track title}' from media metadata.

    Handles multi-artist lists, creators, YouTube Music topic channels, VEVO tags,
    and splits titles formatted as 'Artist - Title' while preventing duplicated artist prefixes.
    """
    raw_artists: Optional[List[str]] = None
    if info.get("artists") and isinstance(info["artists"], list):
        raw_artists = [str(a).strip() for a in info["artists"] if str(a).strip()]
    elif info.get("creators") and isinstance(info["creators"], list):
        raw_artists = [str(c).strip() for c in info["creators"] if str(c).strip()]
    elif info.get("artist"):
        raw_artists = [str(info["artist"]).strip()]
    elif info.get("creator"):
        raw_artists = [str(info["creator"]).strip()]

    channel = str(info.get("channel") or info.get("uploader") or fallback_artist).strip()
    if channel.lower().endswith(" - topic"):
        channel = channel[:-8].strip()
    elif channel.lower().endswith("vevo") and len(channel) > 4:
        channel = channel[:-4].strip() or channel

    raw_title = str(info.get("track") or info.get("alt_title") or info.get("title") or fallback_title).strip()
    sep_pattern = re.compile(r"\s+[\-–—:]\s+")

    has_sep = sep_pattern.search(raw_title)
    if has_sep:
        parts = sep_pattern.split(raw_title, 1)
        left, right = parts[0].strip(), parts[1].strip()
    else:
        left, right = None, raw_title

    if raw_artists:
        artist_str = ", ".join(raw_artists)
        if has_sep and left and (
            any(a.lower() in left.lower() or left.lower() in a.lower() for a in raw_artists)
            or (channel and channel.lower() in left.lower())
        ):
            title_str = right
        else:
            title_str = raw_title
            for a in [artist_str] + raw_artists:
                if a:
                    prefix_pat = re.compile(r"^" + re.escape(a) + r"\s*[\-–—:]\s*", re.IGNORECASE)
                    if prefix_pat.search(title_str):
                        title_str = prefix_pat.sub("", title_str).strip()
                        break
    elif has_sep and left:
        artist_str = left
        title_str = right
    else:
        artist_str = channel or fallback_artist
        title_str = raw_title

    if not artist_str:
        artist_str = channel or fallback_artist or "Unknown Artist"
    if not title_str:
        title_str = raw_title or fallback_title or "Unknown Title"

    clean_artist = sanitize_filename_component(artist_str)
    clean_title = sanitize_filename_component(title_str)
    return clean_artist, clean_title


class CleanMetadataPP(PostProcessor):
    """PostProcessor that sanitizes artist and title metadata before filename formatting and tagging."""

    def __init__(
        self,
        downloader: Any = None,
        default_artist: str = "Unknown Artist",
        default_title: str = "Unknown Title",
        on_metadata_discovered: Optional[Callable[[str, str], None]] = None,
    ):
        super().__init__(downloader)
        self.default_artist = default_artist
        self.default_title = default_title
        self.on_metadata_discovered = on_metadata_discovered

    def run(self, info: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
        artist, title = extract_artist_and_title(
            info,
            fallback_artist=self.default_artist,
            fallback_title=self.default_title,
        )
        info["clean_artist"] = artist
        info["clean_title"] = title
        info["artist"] = artist
        info["track"] = title
        info["title"] = title
        if self.on_metadata_discovered:
            try:
                self.on_metadata_discovered(artist, title)
            except Exception:
                pass
        return [], info


@dataclass
class TrackInfo:
    """Metadata for a single track in a playlist or queue."""

    index: int
    title: str
    artist: str
    duration: int = 0  # seconds
    url: str = ""
    id: str = ""
    status: str = "Pending"  # "Pending", "Downloading", "Converting", "Done", "Error", "Skipped"
    error_message: str = ""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    eta: int = 0
    percent: float = 0.0

    @property
    def duration_formatted(self) -> str:
        if not self.duration or self.duration <= 0:
            return "--:--"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"


@dataclass
class PlaylistInfo:
    """Metadata for a playlist, album, or single track."""

    title: str
    author: str
    url: str
    is_playlist: bool
    track_count: int
    tracks: List[TrackInfo] = field(default_factory=list)
    thumbnail_url: str = ""


@dataclass
class UserPlaylistSummary:
    """Summary of a user's personal playlist from their library."""

    id: str
    title: str
    url: str
    track_count: Optional[int] = None
    channel: str = ""
    thumbnail_url: str = ""



@dataclass
class DownloadProgressUpdate:
    """Real-time progress update event."""

    track_index: int
    total_tracks: int
    track_title: str
    track_artist: str
    track_percent: float
    downloaded_bytes: int
    total_bytes: int
    speed: float
    eta: int
    overall_percent: float
    overall_completed: int
    status_text: str


class DownloadCancelled(Exception):
    """Raised when the user cancels the download."""
    pass


class DependencyError(Exception):
    """Raised when a required system dependency (e.g. FFmpeg) is missing."""
    pass


class YTMusicDownloader:
    """High-level download coordinator."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._cancel_requested = False
        self._active_ydl: Optional[yt_dlp.YoutubeDL] = None

    def cancel(self) -> None:
        """Signal the downloader to stop."""
        self._cancel_requested = True

    def reset_cancel(self) -> None:
        self._cancel_requested = False

    def fetch_info(self, url: str) -> PlaylistInfo:
        """Extract playlist or video metadata without downloading media."""
        ydl_opts: Dict[str, Any] = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "remote_components": ["ejs:github"],
        }
        if self.config.has_cookies():
            ydl_opts["cookiefile"] = self.config.cookies_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("No media information could be extracted from this URL.")

            is_playlist = "_type" in info and info["_type"] in ("playlist", "multi_video") or "entries" in info

            if is_playlist:
                raw_entries = list(info.get("entries") or [])
                tracks = []
                for idx, entry in enumerate(raw_entries, start=1):
                    if not entry:
                        continue
                    artist, title = extract_artist_and_title(
                        entry,
                        fallback_artist=info.get("uploader") or info.get("channel") or "Unknown Artist",
                        fallback_title=f"Track {idx}",
                    )
                    tracks.append(
                        TrackInfo(
                            index=idx,
                            title=title or f"Track {idx}",
                            artist=artist or "Unknown Artist",
                            duration=int(entry.get("duration") or 0),
                            url=entry.get("url") or f"https://music.youtube.com/watch?v={entry.get('id', '')}",
                            id=entry.get("id") or "",
                        )
                    )
                return PlaylistInfo(
                    title=info.get("title") or "Unknown Playlist",
                    author=info.get("uploader") or info.get("channel") or "Unknown Artist",
                    url=url,
                    is_playlist=True,
                    track_count=len(tracks),
                    tracks=tracks,
                    thumbnail_url=info.get("thumbnail") or "",
                )
            else:
                artist, title = extract_artist_and_title(
                    info,
                    fallback_artist="Unknown Artist",
                    fallback_title="Unknown Title",
                )
                track = TrackInfo(
                    index=1,
                    title=title or "Unknown Title",
                    artist=artist or "Unknown Artist",
                    duration=int(info.get("duration") or 0),
                    url=url,
                    id=info.get("id") or "",
                )
                return PlaylistInfo(
                    title=track.title,
                    author=track.artist,
                    url=url,
                    is_playlist=False,
                    track_count=1,
                    tracks=[track],
                    thumbnail_url=info.get("thumbnail") or "",
                )

    def fetch_user_playlists(self) -> List[UserPlaylistSummary]:
        """Fetch list of user's personal and saved playlists from their authenticated feed."""
        if not self.config.has_cookies():
            raise ValueError("You must be logged in with cookies to fetch your personal playlists.")

        ydl_opts: Dict[str, Any] = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "remote_components": ["ejs:github"],
            "cookiefile": self.config.cookies_path,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info("https://www.youtube.com/feed/playlists", download=False)
        except Exception as exc:
            err_msg = str(exc)
            if "401" in err_msg or "Unauthorized" in err_msg or "login" in err_msg.lower():
                # Attempt to auto-sync fresh cookies from an installed browser
                from .browser_auth import extract_from_installed_browser
                synced = False
                for browser_name in ("chrome", "firefox", "brave", "edge", "opera"):
                    try:
                        st = extract_from_installed_browser(browser_name, self.config.cookies_path)
                        if st.is_authenticated:
                            synced = True
                            break
                    except Exception:
                        pass
                if synced:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info("https://www.youtube.com/feed/playlists", download=False)
                else:
                    raise
            else:
                raise

        if not info:
            return []

        raw_entries = list(info.get("entries") or [])
        playlists: List[UserPlaylistSummary] = []
        seen_ids = set()

        for entry in raw_entries:
            if not entry:
                continue
            p_id = entry.get("id") or ""
            if not p_id or p_id in seen_ids:
                continue
            seen_ids.add(p_id)

            url = entry.get("url") or f"https://music.youtube.com/playlist?list={p_id}"
            if "playlist?list=" not in url:
                url = f"https://music.youtube.com/playlist?list={p_id}"
            else:
                url = url.replace("www.youtube.com", "music.youtube.com")

            count = entry.get("playlist_count") or entry.get("item_count")
            playlists.append(
                UserPlaylistSummary(
                    id=p_id,
                    title=entry.get("title") or f"Playlist {p_id}",
                    url=url,
                    track_count=int(count) if count is not None else None,
                    channel=entry.get("uploader") or entry.get("channel") or "",
                    thumbnail_url=entry.get("thumbnail") or "",
                )
            )

        # Prepend Liked Music (YouTube Music LM) for quick access if not present
        if "LM" not in seen_ids:
            liked_music = UserPlaylistSummary(
                id="LM",
                title="♥ Liked Music (YouTube Music)",
                url="https://music.youtube.com/playlist?list=LM",
                channel="YouTube Music",
            )
            playlists.insert(0, liked_music)

        return playlists

    def _build_ydl_opts(
        self,
        output_template: str,
        on_progress: Callable[[Dict[str, Any]], None],
        on_postprocessor: Callable[[Dict[str, Any]], None],
    ) -> Dict[str, Any]:
        """Construct yt-dlp options based on audio quality and re-encoding preferences."""
        opts: Dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [on_progress],
            "postprocessor_hooks": [on_postprocessor],
            "remote_components": ["ejs:github"],
            "writethumbnail": self.config.embed_artwork,
            "windowsfilenames": True,  # Clean safe filenames across OSes
        }

        if self.config.has_cookies():
            opts["cookiefile"] = self.config.cookies_path

        postprocessors = []

        audio_format = self.config.audio_format.lower()
        if audio_format in ("mp3", "m4a", "flac", "opus"):
            pp_extract = {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
            }
            if audio_format == "mp3":
                pp_extract["preferredquality"] = self.config.mp3_quality
            elif audio_format == "m4a":
                pp_extract["preferredquality"] = "256"
            elif audio_format == "opus":
                pp_extract["preferredquality"] = "0"
            postprocessors.append(pp_extract)

        if self.config.embed_metadata:
            postprocessors.append({
                "key": "FFmpegMetadata",
                "add_metadata": True,
            })

        if self.config.embed_artwork:
            postprocessors.append({
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            })

        if postprocessors:
            opts["postprocessors"] = postprocessors

        return opts

    def download_playlist(
        self,
        playlist: PlaylistInfo,
        on_track_update: Callable[[TrackInfo], None],
        on_progress_update: Callable[[DownloadProgressUpdate], None],
        on_log: Callable[[str], None],
    ) -> None:
        """Download playlist or individual tracks with progress feedback."""
        self.reset_cancel()

        # Validate external dependencies before starting download operations
        ffmpeg_ok, ffmpeg_err = verify_ffmpeg_requirement(self.config)
        if not ffmpeg_ok:
            on_log(f"[bold red]Dependency Error:[/bold red] {ffmpeg_err}")
            raise DependencyError(ffmpeg_err)

        total_tracks = len(playlist.tracks)
        completed_count = 0
        dest_dir = Path(self.config.download_dir)

        # Sanitize folder name
        safe_title = "".join(c for c in playlist.title if c.isalnum() or c in (" ", "-", "_", ".")).strip() or "YT-Music"

        if playlist.is_playlist and self.config.auto_create_playlist_folder:
            target_folder = dest_dir / safe_title
        else:
            target_folder = dest_dir

        target_folder.mkdir(parents=True, exist_ok=True)
        on_log(f"Destination directory: {target_folder}")

        for i, track in enumerate(playlist.tracks, start=1):
            if self._cancel_requested:
                on_log("Download operation cancelled by user.")
                track.status = "Skipped"
                on_track_update(track)
                break

            track.status = "Downloading"
            on_track_update(track)
            on_log(f"[{i}/{total_tracks}] Starting: {track.artist} - {track.title}")

            out_tmpl = str(target_folder / SONG_FILENAME_TEMPLATE)

            def progress_hook(d: Dict[str, Any]):
                if self._cancel_requested:
                    raise DownloadCancelled("Cancelled by user")

                status = d.get("status")
                if status == "downloading":
                    downloaded = d.get("downloaded_bytes") or 0
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    speed = d.get("speed") or 0.0
                    eta = d.get("eta") or 0
                    percent = (downloaded / total * 100) if total > 0 else 0.0

                    track.downloaded_bytes = downloaded
                    track.total_bytes = total
                    track.speed = speed
                    track.eta = eta
                    track.percent = percent

                    overall_pct = ((completed_count + (percent / 100.0)) / total_tracks) * 100.0

                    on_progress_update(
                        DownloadProgressUpdate(
                            track_index=i,
                            total_tracks=total_tracks,
                            track_title=track.title,
                            track_artist=track.artist,
                            track_percent=percent,
                            downloaded_bytes=downloaded,
                            total_bytes=total,
                            speed=speed,
                            eta=eta,
                            overall_percent=overall_pct,
                            overall_completed=completed_count,
                            status_text=f"Downloading ({percent:.1f}%)",
                        )
                    )

            def postprocessor_hook(d: Dict[str, Any]):
                if self._cancel_requested:
                    raise DownloadCancelled("Cancelled by user")

                status = d.get("status")
                pp_name = d.get("postprocessor", "")
                if status == "started":
                    track.status = "Converting"
                    on_track_update(track)
                    if "ExtractAudio" in pp_name:
                        action_text = f"Re-encoding to {self.config.audio_format.upper()}..."
                    elif "EmbedThumbnail" in pp_name:
                        action_text = "Embedding cover art..."
                    elif "Metadata" in pp_name:
                        action_text = "Writing ID3/metadata tags..."
                    else:
                        action_text = f"Processing ({pp_name})..."

                    on_log(f"  ↳ {action_text}")
                    overall_pct = ((completed_count + 0.95) / total_tracks) * 100.0
                    on_progress_update(
                        DownloadProgressUpdate(
                            track_index=i,
                            total_tracks=total_tracks,
                            track_title=track.title,
                            track_artist=track.artist,
                            track_percent=95.0,
                            downloaded_bytes=track.total_bytes,
                            total_bytes=track.total_bytes,
                            speed=0.0,
                            eta=0,
                            overall_percent=overall_pct,
                            overall_completed=completed_count,
                            status_text=action_text,
                        )
                    )

            ydl_opts = self._build_ydl_opts(out_tmpl, progress_hook, postprocessor_hook)

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    def on_meta_discovered(discovered_artist: str, discovered_title: str):
                        track.artist = discovered_artist
                        track.title = discovered_title
                        on_track_update(track)

                    clean_pp = CleanMetadataPP(
                        ydl,
                        default_artist=track.artist,
                        default_title=track.title,
                        on_metadata_discovered=on_meta_discovered,
                    )
                    ydl.add_post_processor(clean_pp, when="pre_process")
                    self._active_ydl = ydl
                    ydl.download([track.url])

                completed_count += 1
                track.status = "Done"
                track.percent = 100.0
                on_track_update(track)
                on_log(f"[{i}/{total_tracks}] Finished: {track.title}")

                overall_pct = (completed_count / total_tracks) * 100.0
                on_progress_update(
                    DownloadProgressUpdate(
                        track_index=i,
                        total_tracks=total_tracks,
                        track_title=track.title,
                        track_artist=track.artist,
                        track_percent=100.0,
                        downloaded_bytes=track.total_bytes,
                        total_bytes=track.total_bytes,
                        speed=0.0,
                        eta=0,
                        overall_percent=overall_pct,
                        overall_completed=completed_count,
                        status_text="Finished",
                    )
                )

            except DownloadCancelled:
                track.status = "Skipped"
                on_track_update(track)
                on_log(f"[{i}/{total_tracks}] Cancelled: {track.title}")
                break
            except Exception as e:
                track.status = "Error"
                track.error_message = str(e)
                on_track_update(track)
                on_log(f"[{i}/{total_tracks}] Error downloading {track.title}: {e}")
            finally:
                self._active_ydl = None

        on_log(f"Done! Downloaded {completed_count}/{total_tracks} tracks successfully.")
