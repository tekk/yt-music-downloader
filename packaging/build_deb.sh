#!/usr/bin/env bash
set -euo pipefail

# Build Debian .deb package for yt-music-downloader
# Usage: ./packaging/build_deb.sh <version> <output_dir> [binary_dir]

VERSION="${1:-0.0.4}"
# Strip leading 'v' if present (e.g. v0.0.2 -> 0.0.2)
VERSION="${VERSION#v}"
OUTPUT_DIR="${2:-dist}"
BINARY_DIR="${3:-dist/bin}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PKG_DIR=$(mktemp -d -t yt-music-deb-XXXXXX)
trap 'rm -rf "$PKG_DIR"' EXIT

echo "==> Preparing Debian package structure in $PKG_DIR for version $VERSION..."

# 1. Directory layout
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/512x512/apps"
mkdir -p "$PKG_DIR/usr/share/doc/yt-music-downloader"
mkdir -p "$OUTPUT_DIR"

# 2. Control file
cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: yt-music-downloader
Version: $VERSION
Section: sound
Priority: optional
Architecture: amd64
Maintainer: Peter Javorsky <tekk.sk@gmail.com>
Depends: ffmpeg
Homepage: https://github.com/tekk/yt-music-downloader
Description: YouTube Music Downloader with TUI and Desktop GUI
 Cross-platform application for downloading YouTube Music playlists
 and tracks with highest quality audio, metadata tagging, and modern GUI.
EOF

# 3. Binaries
if [ -d "$BINARY_DIR" ] && [ -f "$BINARY_DIR/yt-music-dl" ] && [ -f "$BINARY_DIR/yt-music-gui" ]; then
    echo "==> Using pre-compiled standalone binaries from $BINARY_DIR..."
    install -m 755 "$BINARY_DIR/yt-music-dl" "$PKG_DIR/usr/bin/yt-music-dl"
    install -m 755 "$BINARY_DIR/yt-music-gui" "$PKG_DIR/usr/bin/yt-music-gui"
else
    echo "==> Installing Python package into package root via pip..."
    python3 -m pip install --no-deps --target "$PKG_DIR/usr/lib/python3/dist-packages" "$ROOT_DIR"
    # Create bin wrappers
    cat > "$PKG_DIR/usr/bin/yt-music-dl" <<'EOF'
#!/usr/bin/env python3
import sys
from yt_music_downloader.cli import main
if __name__ == "__main__":
    main()
EOF
    chmod 755 "$PKG_DIR/usr/bin/yt-music-dl"

    cat > "$PKG_DIR/usr/bin/yt-music-gui" <<'EOF'
#!/usr/bin/env python3
import sys
from yt_music_downloader.gui.app import main
if __name__ == "__main__":
    main()
EOF
    chmod 755 "$PKG_DIR/usr/bin/yt-music-gui"
fi

# 4. Desktop entry & Icon & License
install -m 644 "$SCRIPT_DIR/yt-music-downloader.desktop" "$PKG_DIR/usr/share/applications/yt-music-downloader.desktop"
if [ -f "$SCRIPT_DIR/yt-music-downloader.png" ]; then
    install -m 644 "$SCRIPT_DIR/yt-music-downloader.png" "$PKG_DIR/usr/share/icons/hicolor/512x512/apps/yt-music-downloader.png"
fi
if [ -f "$ROOT_DIR/README.md" ]; then
    install -m 644 "$ROOT_DIR/README.md" "$PKG_DIR/usr/share/doc/yt-music-downloader/README.md"
fi

# 5. Build .deb package
DEB_FILE="$OUTPUT_DIR/yt-music-downloader_${VERSION}_amd64.deb"
echo "==> Building $DEB_FILE..."
dpkg-deb --build --root-owner-group "$PKG_DIR" "$DEB_FILE"
echo "==> Successfully created $DEB_FILE!"
