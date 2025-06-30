# tests/test_utils.py

import sys
import os

from utils import resource_path


def test_resource_path_dev_environment(mocker):
    """
    Test that resource_path returns the correct absolute path in a normal environment.
    """
    # ARRANGE
    # --- FIX: Safely ensure sys._MEIPASS does not exist for this test ---
    # raising=False prevents an error if the attribute doesn't exist to begin with.
    mocker.patch.delattr(sys, "_MEIPASS", raising=False)

    # ACT
    path = resource_path("assets/icon.ico")

    # ASSERT
    assert path == os.path.abspath(os.path.join(".", "assets/icon.ico"))


def test_resource_path_pyinstaller_bundle(mocker):
    """
    Test that resource_path returns the correct temp path in a PyInstaller bundle.
    """
    # ARRANGE
    fake_temp_path = "/tmp/_MEI12345"
    mocker.patch.object(sys, "_MEIPASS", fake_temp_path, create=True)

    # ACT
    path = resource_path("assets/icon.ico")

    # ASSERT
    assert path == os.path.join(fake_temp_path, "assets/icon.ico")
