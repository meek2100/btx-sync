# utils.py
# A place for helper functions that can be used across the application.

import sys
import os


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to a resource, which works for development environments
    and for the bundled executable created by PyInstaller.
    """
    try:
        # PyInstaller creates a temp folder and stores its path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If not running in a PyInstaller bundle, use the normal absolute path
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def is_production_environment() -> bool:
    """
    Checks if the application is running as a bundled executable by checking
    for the _MEIPASS attribute set by PyInstaller.
    """
    return hasattr(sys, "_MEIPASS")
