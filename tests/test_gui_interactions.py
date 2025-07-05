# tests/test_gui_interactions.py

import pytest
import requests
from unittest.mock import MagicMock

from gui_settings import SettingsWindow
from app import App


@pytest.fixture
def mock_settings_window(mocker):
    """Mocks the full initialization of the SettingsWindow for interaction testing."""
    mocker.patch.object(SettingsWindow, "__init__", lambda s, *a, **kw: None)
    settings_window = SettingsWindow(None)
    settings_window.advanced_checkbox = MagicMock()
    settings_window.advanced_frame = MagicMock()
    settings_window.geometry = MagicMock()
    return settings_window


def test_toggle_advanced_settings_show(mock_settings_window):
    """Verify that checking the box shows the advanced settings frame."""
    mock_settings_window.advanced_checkbox.get.return_value = 1
    SettingsWindow.toggle_advanced_settings(mock_settings_window)
    mock_settings_window.advanced_frame.grid.assert_called_once()
    mock_settings_window.advanced_frame.grid_remove.assert_not_called()


def test_toggle_advanced_settings_hide(mock_settings_window):
    """Verify that unchecking the box hides the advanced settings frame."""
    mock_settings_window.advanced_checkbox.get.return_value = 0
    SettingsWindow.toggle_advanced_settings(mock_settings_window)
    mock_settings_window.advanced_frame.grid.assert_not_called()
    mock_settings_window.advanced_frame.grid_remove.assert_called_once()


def test_braze_connection_handles_network_error(mocker):
    """
    Verify the Braze connection test reports failure on a network error.
    """
    # ARRANGE
    mocker.patch(
        "requests.Session.get", side_effect=requests.exceptions.RequestException
    )
    # FIX: Prevent the GUI from initializing, just like in the other test.
    mocker.patch.object(SettingsWindow, "__init__", lambda s, *a, **kw: None)
    container = SettingsWindow(None)

    # ACT
    status, msg = container._test_braze_connection("key", "endpoint")

    # ASSERT
    assert status == "FAILED"
    assert "Could not connect to Braze" in msg


def test_open_help_file_handles_error(mocker):
    """
    Verify that if opening the help file fails, an error message is shown.
    """
    # ARRANGE
    mocker.patch("app.resource_path", return_value="dummy/path/README.md")
    mocker.patch("app.webbrowser.open", side_effect=Exception("File not found"))
    mock_showerror = mocker.patch("app.messagebox.showerror")
    # FIX: Prevent the App's __init__ method from running to avoid the TclError.
    mocker.patch.object(App, "__init__", lambda s: None)
    app_instance = App()

    # ACT
    app_instance.open_help_file()

    # ASSERT
    mock_showerror.assert_called_once()
    assert "Could not open help file" in mock_showerror.call_args[0][1]
