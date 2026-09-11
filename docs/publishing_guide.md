# 🚀 Publishing & Installation Guide

This guide explains how to publish **YouTube Music Downloader** so that users worldwide can install it using `pipx`, `uv tool`, or `pip`, or download standalone precompiled binaries.

---

## 📦 1. How Python Tool Installation Works

When published to PyPI ([Python Package Index](https://pypi.org)), users can install the application with a single command into an isolated environment without dependency conflicts.

The package registers two entry points:
- `yt-music-dl` — Interactive Terminal User Interface (TUI)
- `yt-music-gui` — Modern Desktop GUI

---

## 🔑 2. Publishing to PyPI

### Step 1: Create a PyPI Account
1. If you don't already have one, create an account on [pypi.org](https://pypi.org/account/register/).
2. Enable Two-Factor Authentication (2FA), which is required by PyPI.

---

### Option A: Manual Publishing via `uv` or `twine` (Quickest)

You can build and publish directly from your local terminal:

#### 1. Generate a PyPI API Token
1. Go to [pypi.org/manage/account/token/](https://pypi.org/manage/account/token/).
2. Set token name (e.g., `yt-music-downloader-local`).
3. For a new project, select **Entire account (all projects)**.
4. Copy the generated token (`pypi-...`).

#### 2. Build the Package
```bash
# Build both sdist (.tar.gz) and universal wheel (.whl)
uv build
# Or with standard build:
python -m build
```
This produces:
- `dist/yt_music_downloader-0.0.3.tar.gz`
- `dist/yt_music_downloader-0.0.3-py3-none-any.whl`

#### 3. Upload to PyPI
```bash
# Using uv (fastest):
uv publish --token <your-pypi-token>

# Or using twine:
pip install twine
twine upload dist/*
```
Once uploaded, your project will be live immediately at `https://pypi.org/project/yt-music-downloader/`!

---

### Option B: Automatic Publishing via GitHub Actions (Trusted Publisher)

PyPI supports **Trusted Publishing (OIDC)**, eliminating the need to store static API tokens or passwords in GitHub secrets.

#### 1. Configure Trusted Publisher on PyPI
1. Go to [PyPI Publishing Settings](https://pypi.org/manage/account/publishing/).
2. Under **"Add a new publisher"**, select **GitHub**.
3. Fill in:
   - **PyPI Project Name**: `yt-music-downloader`
   - **Owner**: `tekk`
   - **Repository name**: `yt-music-downloader`
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi`
4. Click **Add**.

#### 2. Trigger
Whenever you push a `v*` tag, GitHub Actions will automatically build and publish to PyPI securely.

---

## 💻 3. How Users Install the Application

Once published to PyPI, users can install via any of the following methods:

### Method 1: `pipx` (Recommended for Command-Line & Desktop Apps)
`pipx` automatically creates an isolated virtual environment for the app and exposes the executables on the user's `PATH`:

```bash
# Install
pipx install yt-music-downloader

# Run Terminal TUI:
yt-music-dl

# Run Desktop GUI:
yt-music-gui

# Upgrade in the future:
pipx upgrade yt-music-downloader
```

---

### Method 2: `uv tool` (Ultra-Fast)
If the user has `uv` installed:

```bash
# Install globally:
uv tool install yt-music-downloader

# Run TUI:
yt-music-dl

# Run GUI:
yt-music-gui

# Or run directly without permanent installation:
uvx --from yt-music-downloader yt-music-gui
```

---

### Method 3: Standard `pip` (Virtualenv)
```bash
# In an activated virtualenv:
pip install yt-music-downloader
yt-music-dl
yt-music-gui
```

---

## 🌐 4. Installing Directly from GitHub (No PyPI Required!)

Users can also install directly from your GitHub repository right now without waiting for PyPI:

```bash
# Via pipx:
pipx install git+https://github.com/tekk/yt-music-downloader.git

# Via uv:
uv tool install git+https://github.com/tekk/yt-music-downloader.git

# Via standard pip:
pip install git+https://github.com/tekk/yt-music-downloader.git
```

---

## 💽 5. Standalone Precompiled Binaries (No Python Needed)

Every time you push a `v*` tag (e.g. `v0.0.3`), the GitHub Actions release workflow compiles standalone binaries attached to the GitHub Release:

1. **Windows x64 / ARM64**:
   - Download `yt-music-downloader-v0.0.3-windows-x64.zip` (or arm64).
   - Extract and double-click `yt-music-gui.exe` (or run `yt-music-dl.exe` in PowerShell / Windows Terminal).

2. **Linux AppImage**:
   - Download `yt-music-downloader-v0.0.3-linux-x86_64.AppImage`.
   - Make executable and run:
     ```bash
     chmod +x yt-music-downloader-*-linux-x86_64.AppImage
     ./yt-music-downloader-*-linux-x86_64.AppImage
     ```

3. **Debian / Ubuntu (.deb)**:
   - Download `yt-music-downloader_0.0.3_amd64.deb`.
   - Install with:
     ```bash
     sudo dpkg -i yt-music-downloader_*_amd64.deb
     sudo apt-get install -f  # resolves ffmpeg if missing
     ```
   - Launches from desktop application menu or terminal (`yt-music-gui` / `yt-music-dl`).
