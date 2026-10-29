from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


def visible_lines(value: str) -> list[str]:
    text = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).replace("\u00a0", " ").splitlines() or [""]


def find_windows_font(font_family: str) -> Path | None:
    fonts = Path("C:/Windows/Fonts")
    if not fonts.exists():
        return None
    aliases = {
        "arial": ["arial.ttf"],
        "times new roman": ["times.ttf"],
        "calibri": ["calibri.ttf"],
    }
    candidates = aliases.get(font_family.lower(), [f"{font_family.replace(' ', '')}.ttf"])
    for candidate in candidates:
        path = fonts / candidate
        if path.exists():
            return path
    return None


def measure_text(value: str, font_family: str, font_size: float, line_height: float = 1.2) -> Dict[str, Any]:
    """Measure visible text with Pillow when available; return an explicit fallback otherwise."""
    lines = visible_lines(value)
    font_path = find_windows_font(font_family)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(str(font_path or font_family), max(1, round(font_size)))
        widths = []
        for line in lines:
            box = font.getbbox(line or " ")
            widths.append(float(box[2] - box[0]))
        return {
            "width": max(widths, default=0.0),
            "height": len(lines) * float(font_size) * float(line_height),
            "font_family": font_family,
            "font_file": str(font_path) if font_path else None,
            "font_size": font_size,
            "line_height": line_height,
            "engine": "Pillow",
            "fallback": font_path is None,
        }
    except (ImportError, OSError):
        return {
            "width": max((len(line) for line in lines), default=0) * float(font_size) * 0.6,
            "height": len(lines) * float(font_size) * float(line_height),
            "font_family": font_family,
            "font_file": str(font_path) if font_path else None,
            "font_size": font_size,
            "line_height": line_height,
            "engine": "explicit-approximation",
            "fallback": True,
        }
