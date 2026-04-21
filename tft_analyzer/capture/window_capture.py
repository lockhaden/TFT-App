from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from PIL import ImageGrab

LOGGER = logging.getLogger(__name__)


@dataclass
class CaptureResult:
    image_bgr: np.ndarray
    source: str


def list_windows() -> list[str]:
    try:
        import win32gui
    except Exception:
        return []

    titles: list[str] = []

    def callback(hwnd: int, _: object) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            if title:
                titles.append(title)

    win32gui.EnumWindows(callback, None)
    return sorted(set(titles))


def capture_screen_region(region: Iterable[int] | None = None) -> CaptureResult:
    bbox = tuple(region) if region else None
    image = ImageGrab.grab(bbox=bbox)
    rgb = np.array(image.convert("RGB"))
    return CaptureResult(rgb[:, :, ::-1].copy(), "region" if bbox else "full_screen")


def capture_window(title_contains: str) -> CaptureResult:
    try:
        import win32gui
    except Exception as exc:
        raise RuntimeError("pywin32 is required for window-title capture") from exc

    matches: list[tuple[int, str]] = []

    def callback(hwnd: int, _: object) -> None:
        title = win32gui.GetWindowText(hwnd)
        if win32gui.IsWindowVisible(hwnd) and title_contains.lower() in title.lower():
            matches.append((hwnd, title))

    win32gui.EnumWindows(callback, None)
    if not matches:
        raise RuntimeError(f"No visible window title contains '{title_contains}'")

    hwnd, title = matches[0]
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    if right <= left or bottom <= top:
        raise RuntimeError(f"Window '{title}' has an invalid capture rectangle")

    image = ImageGrab.grab(bbox=(left, top, right, bottom))
    rgb = np.array(image.convert("RGB"))
    return CaptureResult(rgb[:, :, ::-1].copy(), f"window:{title}")
