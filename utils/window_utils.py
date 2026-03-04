"""Window and DPI management utilities."""
import ctypes
import json
import os
import sys
from typing import Optional

from utils.constants import Dimensions
import pygame


def set_dpi_awareness() -> None:
    """
    Attempt to mark the process as DPI-aware on Windows.
    Called before creating the pygame window or initializing SDL so that
    the underlying window is created with the correct size.
    Windows can apply per-monitor DPI scaling (100%, 125%, 150%, etc.)
    """
    if sys.platform != "win32":
        return
    # modern Windows 8.1+ has SetProcessDpiAwareness
    try:
        # 0=UNAWARE, 1=SYSTEM_AWARE, 2=PER_MONITOR_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # fallback to older API
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def get_dpi_scale(hwnd: int | None = None) -> float:
    """
    Return the current DPI scaling factor for a window.
    On Windows the default DPI is 96, so a DPI report of 120 corresponds
    to a scale factor of 1.25 (125%). If the function fails for any reason,
    it defaults to a scale factor of 1.0 (100%).
    """
    if sys.platform != "win32":
        return 1.0

    try:
        if hwnd is None:
            hwnd = pygame.display.get_wm_info()["window"]
        # Windows 10+ API
        dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
    except Exception:
        try:
            # fall back to device context query (older Windows)
            dc = ctypes.windll.user32.GetDC(hwnd)
            LOGPIXELSX = 88
            dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, LOGPIXELSX)
            ctypes.windll.user32.ReleaseDC(hwnd, dc)
        except Exception:
            dpi = 96
    return float(dpi) / 96.0


def user_data_path(filename: str) -> str:
    """
    Returns a writable path for user-generated files.
    Works both for normal Python runs and PyInstaller executables.
    Used for storing user-generated, writable data like preferences, logs, or saved states.
    Points to a permanent writable directory.
    """
    base_dir = os.path.join(os.path.expanduser("~"), ".prefire")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, filename)


def save_window_state(is_maximized: bool) -> None:
    """Save window maximized state to user data."""
    state = {"maximized": is_maximized}
    path = user_data_path("window_state.json")
    with open(path, "w") as f:
        json.dump(state, f)


def load_window_state() -> bool:
    """Load window maximized state from user data."""
    path = user_data_path("window_state.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            state = json.load(f)
            return state.get("maximized", False)
    return False


def loadImage(image_directory: str, csv_directory: str, i: int) -> tuple[Optional[pygame.Surface], str]:
    """
    Load background image and CSV filename.
    
    :param image_directory: Image Directory
    :param csv_directory: CSV Directory
    :param i: layout_{i}.png from image_directory and layout_{i}.csv from csv_directory
    :return: BG_IMAGE, csv_filename
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        img_filename = f"{image_directory}/layout_{i}.png"
        csv_filename = f"{csv_directory}/layout_{i}.csv"
        BG_IMAGE = pygame.image.load(img_filename).convert_alpha()
        # scale to the logical grid width then apply DPI factor so the image remains sharp on high-DPI displays
        scale = get_dpi_scale()
        size = int(Dimensions.WIDTH.value * scale)
        BG_IMAGE = pygame.transform.scale(BG_IMAGE, (size, size))
        BG_IMAGE.set_alpha(0)
    except:
        logger.warning("Background image not found, proceeding without it.")
        BG_IMAGE = None

    return BG_IMAGE, csv_filename
