# tests/test_utils.py

import sys
import os

from utils import resource_path


def test_resource_path_dev_environment(monkeypatch):
    """
    Test that resource_path returns the correct absolute path in a normal environment.
    """
    # ARRANGE
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    # --- FIX: Construct the relative path using os.path.join ---
    relative_path = os.path.join("assets", "icon.ico")

    # ACT
    path = resource_path(relative_path)

    # ASSERT
    assert path == os.path.abspath(relative_path)


def test_resource_path_pyinstaller_bundle(mocker):
    """
    Test that resource_path returns the correct temp path in a PyInstaller bundle.
    """
    # ARRANGE
    fake_temp_path = "/tmp/_MEI12345"
    mocker.patch.object(sys, "_MEIPASS", fake_temp_path, create=True)
    relative_path = os.path.join("assets", "icon.ico")

    # ACT
    path = resource_path(relative_path)

    # ASSERT
    # Use os.path.join to create the expected path with the correct separators
    assert path == os.path.join(fake_temp_path, "assets", "icon.ico")
