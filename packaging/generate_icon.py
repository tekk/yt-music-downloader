#!/usr/bin/env python3
"""Generate application icon for YouTube Music Downloader."""

import os
import sys
from pathlib import Path

# Headless mode for Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)


def create_app_icon(size: int = 512) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # 1. Outer Dark Rounded Card (Squircle)
    margin = size * 0.04
    card_rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    card_path = QPainterPath()
    card_radius = size * 0.22
    card_path.addRoundedRect(card_rect, card_radius, card_radius)

    # Gradient background
    bg_gradient = QLinearGradient(0, 0, size, size)
    bg_gradient.setColorAt(0.0, QColor("#1E1E24"))
    bg_gradient.setColorAt(1.0, QColor("#101012"))
    painter.fillPath(card_path, QBrush(bg_gradient))

    # Outer border
    border_pen = QPen(QColor("#33333C"), size * 0.015)
    painter.strokePath(card_path, border_pen)

    # 2. YouTube Music Red Glow Circle
    center_x, center_y = size / 2.0, size / 2.0
    radius = size * 0.32
    circle_gradient = QLinearGradient(center_x, center_y - radius, center_x, center_y + radius)
    circle_gradient.setColorAt(0.0, QColor("#FF1744"))  # Vibrant YT red
    circle_gradient.setColorAt(1.0, QColor("#D50000"))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(circle_gradient))
    painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

    # Inner subtle concentric ring
    inner_ring_pen = QPen(QColor(255, 255, 255, 60), size * 0.012)
    painter.setPen(inner_ring_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(center_x, center_y), radius * 0.65, radius * 0.65)

    # 3. Center Play Triangle + Music Note
    # Play Triangle
    tri_path = QPainterPath()
    tri_size = radius * 0.45
    tri_x = center_x - tri_size * 0.35
    tri_y = center_y
    tri_path.moveTo(tri_x, tri_y - tri_size * 0.65)
    tri_path.lineTo(tri_x + tri_size * 1.0, tri_y)
    tri_path.lineTo(tri_x, tri_y + tri_size * 0.65)
    tri_path.closeSubpath()

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#FFFFFF"))
    painter.fillPath(tri_path, QBrush(QColor("#FFFFFF")))

    # 4. Cyan Accent Accent Dot (Top right)
    dot_radius = size * 0.035
    dot_x = center_x + radius * 0.72
    dot_y = center_y - radius * 0.72
    painter.setBrush(QBrush(QColor("#00E5FF")))
    painter.drawEllipse(QPointF(dot_x, dot_y), dot_radius, dot_radius)

    painter.end()
    return image


def main():
    app = QGuiApplication(sys.argv)
    img = create_app_icon(512)

    pkg_dir = Path(__file__).parent
    pkg_dir.mkdir(parents=True, exist_ok=True)
    icon_pkg = pkg_dir / "yt-music-downloader.png"
    img.save(str(icon_pkg), "PNG")
    print(f"Saved icon: {icon_pkg}")

    img_dir = pkg_dir.parent / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    icon_img = img_dir / "icon.png"
    img.save(str(icon_img), "PNG")
    print(f"Saved icon: {icon_img}")


if __name__ == "__main__":
    main()
