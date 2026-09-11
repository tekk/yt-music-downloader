#!/usr/bin/env bash
set -euo pipefail

# Build Linux .AppImage package for yt-music-downloader
# Usage: ./packaging/build_appimage.sh <version> <output_dir> [binary_dir]

VERSION="${1:-0.0.3}"
OUTPUT_DIR="${2:-dist}"
BINARY_DIR="${3:-dist/bin}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

APPDIR=$(mktemp -d -t yt-music-appdir-XXXXXX)
trap 'rm -rf "$APPDIR"' EXIT

echo "==> Preparing AppDir structure in $APPDIR for version $VERSION..."

mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/512x512/apps"
mkdir -p "$OUTPUT_DIR"

# 1. Copy binaries
if [ -d "$BINARY_DIR" ] && [ -f "$BINARY_DIR/yt-music-gui" ]; then
    echo "==> Using pre-compiled binaries from $BINARY_DIR..."
    cp -r "$BINARY_DIR"/* "$APPDIR/usr/bin/"
else
    echo "==> Error: Standalone binary directory not found at $BINARY_DIR" >&2
    exit 1
fi

# 2. Copy Desktop file and Icons
cp "$SCRIPT_DIR/yt-music-downloader.desktop" "$APPDIR/yt-music-downloader.desktop"
if [ -f "$SCRIPT_DIR/yt-music-downloader.png" ]; then
    cp "$SCRIPT_DIR/yt-music-downloader.png" "$APPDIR/yt-music-downloader.png"
    cp "$SCRIPT_DIR/yt-music-downloader.png" "$APPDIR/usr/share/icons/hicolor/512x512/apps/yt-music-downloader.png"
fi

# 3. Create AppRun script
cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH:-}"

if [ "${1:-}" = "--tui" ] || [ "${1:-}" = "-t" ]; then
    shift
    exec "${HERE}/usr/bin/yt-music-dl" "$@"
else
    exec "${HERE}/usr/bin/yt-music-gui" "$@"
fi
EOF
chmod +x "$APPDIR/AppRun"

# 4. Download appimagetool if not available
if ! command -v appimagetool &> /dev/null; then
    echo "==> Downloading appimagetool..."
    curl -fsSL -o /tmp/appimagetool "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x /tmp/appimagetool
    APPIMAGETOOL="/tmp/appimagetool"
else
    APPIMAGETOOL="appimagetool"
fi

# 5. Build AppImage
OUTPUT_FILE="$OUTPUT_DIR/yt-music-downloader-${VERSION}-linux-x86_64.AppImage"
echo "==> Packaging AppImage into $OUTPUT_FILE..."
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUTPUT_FILE"
chmod +x "$OUTPUT_FILE"

echo "==> Successfully created $OUTPUT_FILE!"
